#include "atlas/node_agent/vital_transport.hpp"

#include <array>
#include <cstdio>
#include <limits>
#include <stdexcept>
#include <utility>

#include <mbedtls/ctr_drbg.h>
#include <mbedtls/error.h>
#include <mbedtls/entropy.h>
#include <mbedtls/net_sockets.h>
#include <mbedtls/pk.h>
#include <mbedtls/ssl.h>
#include <mbedtls/x509_crt.h>

namespace atlas::node_agent {
namespace {

struct TlsState {
  mbedtls_net_context net{};
  mbedtls_ssl_context ssl{};
  mbedtls_ssl_config conf{};
  mbedtls_x509_crt ca{};
  mbedtls_x509_crt cert{};
  mbedtls_pk_context key{};
  mbedtls_entropy_context entropy{};
  mbedtls_ctr_drbg_context drbg{};

  TlsState() {
    mbedtls_net_init(&net);
    mbedtls_ssl_init(&ssl);
    mbedtls_ssl_config_init(&conf);
    mbedtls_x509_crt_init(&ca);
    mbedtls_x509_crt_init(&cert);
    mbedtls_pk_init(&key);
    mbedtls_entropy_init(&entropy);
    mbedtls_ctr_drbg_init(&drbg);
  }
  ~TlsState() {
    mbedtls_net_free(&net);
    mbedtls_ssl_free(&ssl);
    mbedtls_ssl_config_free(&conf);
    mbedtls_x509_crt_free(&ca);
    mbedtls_x509_crt_free(&cert);
    mbedtls_pk_free(&key);
    mbedtls_ctr_drbg_free(&drbg);
    mbedtls_entropy_free(&entropy);
  }
};

std::string error_name(int code) {
  char buffer[160]{};
  mbedtls_strerror(code, buffer, sizeof(buffer));
  return buffer;
}

bool load_credentials(TlsState& state, const TlsCredentials& credentials,
                      const char* personalization, std::string& reason) {
  int rc = mbedtls_ctr_drbg_seed(&state.drbg, mbedtls_entropy_func, &state.entropy,
                                 reinterpret_cast<const unsigned char*>(personalization),
                                 std::char_traits<char>::length(personalization));
  if (rc != 0) { reason = "rng_init_failed:" + error_name(rc); return false; }
  rc = mbedtls_x509_crt_parse_file(&state.ca, credentials.ca_cert.string().c_str());
  if (rc != 0) { reason = "ca_load_failed:" + error_name(rc); return false; }
  rc = mbedtls_x509_crt_parse_file(&state.cert, credentials.certificate.string().c_str());
  if (rc != 0) { reason = "cert_load_failed:" + error_name(rc); return false; }
  rc = mbedtls_pk_parse_keyfile(&state.key, credentials.private_key.string().c_str(), nullptr,
                                mbedtls_ctr_drbg_random, &state.drbg);
  if (rc != 0) { reason = "key_load_failed:" + error_name(rc); return false; }
  return true;
}
bool configure_tls(TlsState& state, int endpoint, std::chrono::milliseconds timeout,
                   std::string& reason) {
  int rc = mbedtls_ssl_config_defaults(&state.conf, endpoint, MBEDTLS_SSL_TRANSPORT_STREAM,
                                       MBEDTLS_SSL_PRESET_DEFAULT);
  if (rc != 0) { reason = "ssl_config_failed:" + error_name(rc); return false; }
  mbedtls_ssl_conf_authmode(&state.conf, MBEDTLS_SSL_VERIFY_REQUIRED);
  mbedtls_ssl_conf_ca_chain(&state.conf, &state.ca, nullptr);
  mbedtls_ssl_conf_rng(&state.conf, mbedtls_ctr_drbg_random, &state.drbg);
  mbedtls_ssl_conf_read_timeout(&state.conf,
      static_cast<std::uint32_t>(timeout.count()));
  rc = mbedtls_ssl_conf_own_cert(&state.conf, &state.cert, &state.key);
  if (rc != 0) { reason = "ssl_own_cert_failed:" + error_name(rc); return false; }
  rc = mbedtls_ssl_setup(&state.ssl, &state.conf);
  if (rc != 0) { reason = "ssl_setup_failed:" + error_name(rc); return false; }
  mbedtls_ssl_set_bio(&state.ssl, &state.net, mbedtls_net_send,
                      mbedtls_net_recv, mbedtls_net_recv_timeout);
  return true;
}

bool handshake(TlsState& state, std::string& reason) {
  while (true) {
    const int rc = mbedtls_ssl_handshake(&state.ssl);
    if (rc == 0) return true;
    if (rc == MBEDTLS_ERR_SSL_WANT_READ || rc == MBEDTLS_ERR_SSL_WANT_WRITE) continue;
    reason = "tls_handshake_failed:" + error_name(rc);
    return false;
  }
}

bool ssl_write_all(TlsState& state, const unsigned char* data, std::size_t size,
                   std::string& reason) {
  std::size_t offset = 0;
  while (offset < size) {
    const int rc = mbedtls_ssl_write(&state.ssl, data + offset, size - offset);
    if (rc > 0) { offset += static_cast<std::size_t>(rc); continue; }
    if (rc == MBEDTLS_ERR_SSL_WANT_READ || rc == MBEDTLS_ERR_SSL_WANT_WRITE) continue;
    reason = "tls_write_failed:" + error_name(rc);
    return false;
  }
  return true;
}
bool ssl_read_exact(TlsState& state, unsigned char* data, std::size_t size,
                    std::string& reason) {
  std::size_t offset = 0;
  while (offset < size) {
    const int rc = mbedtls_ssl_read(&state.ssl, data + offset, size - offset);
    if (rc > 0) { offset += static_cast<std::size_t>(rc); continue; }
    if (rc == MBEDTLS_ERR_SSL_WANT_READ || rc == MBEDTLS_ERR_SSL_WANT_WRITE) continue;
    reason = rc == MBEDTLS_ERR_SSL_TIMEOUT ? "tls_read_timeout" :
             "tls_read_failed:" + error_name(rc);
    return false;
  }
  return true;
}

std::string peer_common_name(const mbedtls_x509_crt* peer) {
  if (!peer) return {};
  char subject[512]{};
  if (mbedtls_x509_dn_gets(subject, sizeof(subject), &peer->subject) <= 0) return {};
  const std::string value(subject);
  const auto pos = value.find("CN=");
  if (pos == std::string::npos) return {};
  const auto start = pos + 3;
  const auto end = value.find(',', start);
  return value.substr(start, end == std::string::npos ? std::string::npos : end - start);
}

std::array<unsigned char, 4> encode_size(std::size_t size) {
  return {static_cast<unsigned char>((size >> 24) & 0xff),
          static_cast<unsigned char>((size >> 16) & 0xff),
          static_cast<unsigned char>((size >> 8) & 0xff),
          static_cast<unsigned char>(size & 0xff)};
}

std::size_t decode_size(const std::array<unsigned char, 4>& bytes) {
  return (static_cast<std::size_t>(bytes[0]) << 24) |
         (static_cast<std::size_t>(bytes[1]) << 16) |
         (static_cast<std::size_t>(bytes[2]) << 8) |
         static_cast<std::size_t>(bytes[3]);
}

}  // namespace
VitalClient::VitalClient(VitalClientConfig config, TlsCredentials credentials)
    : config_(std::move(config)), credentials_(std::move(credentials)) {
  if (config_.host.empty() || config_.port == 0 || config_.max_frame_bytes == 0 ||
      config_.timeout.count() <= 0 || config_.expected_server_name.empty()) {
    throw std::invalid_argument("invalid vital client config");
  }
}

VitalSendResult VitalClient::send_frame(const std::string& frame) const {
  if (frame.size() > config_.max_frame_bytes) return {false, "frame_too_large"};
  TlsState state;
  std::string reason;
  if (!load_credentials(state, credentials_, "atlas-vital-client", reason)) return {false, reason};
  if (!configure_tls(state, MBEDTLS_SSL_IS_CLIENT, config_.timeout, reason)) return {false, reason};
  if (mbedtls_ssl_set_hostname(&state.ssl, config_.expected_server_name.c_str()) != 0)
    return {false, "server_name_setup_failed"};
  const auto port = std::to_string(config_.port);
  int rc = mbedtls_net_connect(&state.net, config_.host.c_str(), port.c_str(), MBEDTLS_NET_PROTO_TCP);
  if (rc != 0) return {false, "tcp_connect_failed:" + error_name(rc)};
  if (!handshake(state, reason)) return {false, reason};
  if (mbedtls_ssl_get_verify_result(&state.ssl) != 0) return {false, "server_certificate_untrusted"};
  const auto size = encode_size(frame.size());
  if (!ssl_write_all(state, size.data(), size.size(), reason)) return {false, reason};
  if (!ssl_write_all(state, reinterpret_cast<const unsigned char*>(frame.data()), frame.size(), reason))
    return {false, reason};
  mbedtls_ssl_close_notify(&state.ssl);
  return {true, ""};
}
VitalServer::VitalServer(VitalServerConfig config, TlsCredentials credentials)
    : config_(std::move(config)), credentials_(std::move(credentials)) {
  if (config_.bind_host.empty() || config_.port == 0 || config_.max_frame_bytes == 0 ||
      config_.timeout.count() <= 0 || config_.expected_peer_node_id.empty()) {
    throw std::invalid_argument("invalid vital server config");
  }
}

VitalReceiveResult VitalServer::receive_once() const {
  TlsState state;
  mbedtls_net_context listener{};
  mbedtls_net_init(&listener);
  struct ListenerGuard { mbedtls_net_context* ctx; ~ListenerGuard() { mbedtls_net_free(ctx); } } guard{&listener};
  std::string reason;
  if (!load_credentials(state, credentials_, "atlas-vital-server", reason)) return {false, reason, {}, {}};
  if (!configure_tls(state, MBEDTLS_SSL_IS_SERVER, config_.timeout, reason)) return {false, reason, {}, {}};
  const auto port = std::to_string(config_.port);
  int rc = mbedtls_net_bind(&listener, config_.bind_host.c_str(), port.c_str(), MBEDTLS_NET_PROTO_TCP);
  if (rc != 0) return {false, "tcp_bind_failed:" + error_name(rc), {}, {}};
  rc = mbedtls_net_accept(&listener, &state.net, nullptr, 0, nullptr);
  if (rc != 0) return {false, "tcp_accept_failed:" + error_name(rc), {}, {}};
  if (!handshake(state, reason)) return {false, reason, {}, {}};
  if (mbedtls_ssl_get_verify_result(&state.ssl) != 0) return {false, "client_certificate_untrusted", {}, {}};
  const auto* peer = mbedtls_ssl_get_peer_cert(&state.ssl);
  const auto peer_id = peer_common_name(peer);
  if (peer_id != config_.expected_peer_node_id)
    return {false, "peer_identity_mismatch", peer_id, {}};

  std::array<unsigned char, 4> size_bytes{};
  if (!ssl_read_exact(state, size_bytes.data(), size_bytes.size(), reason)) return {false, reason, peer_id, {}};
  const auto frame_size = decode_size(size_bytes);
  if (frame_size > config_.max_frame_bytes) return {false, "frame_too_large", peer_id, {}};
  std::string frame(frame_size, '\0');
  if (!ssl_read_exact(state, reinterpret_cast<unsigned char*>(frame.data()), frame.size(), reason))
    return {false, reason, peer_id, {}};
  mbedtls_ssl_close_notify(&state.ssl);
  return {true, "", peer_id, std::move(frame)};
}

}  // namespace atlas::node_agent
