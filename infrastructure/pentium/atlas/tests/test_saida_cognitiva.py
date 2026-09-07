import unittest

from infrastructure.pentium.atlas.saida_cognitiva import parse_resposta_llm


class SaidaCognitivaTests(unittest.TestCase):
    def test_parseia_resposta_estruturada_com_intencao(self):
        resposta = parse_resposta_llm('{"versao_schema":1,"texto":"Vou verificar.","resumo":null,"intencao":"get_host_status","parametros_intencao":{"host":"core"},"confianca":0.9,"motivo":"interacao_humana","requer_confirmacao":false}')
        self.assertEqual("get_host_status", resposta.intencao)
        self.assertEqual({"host": "core"}, resposta.parametros_intencao)
        self.assertEqual(0.9, resposta.confianca)

    def test_rejeita_json_malformado_schema_e_confianca_invalidos(self):
        for payload in (
            "nao-json",
            '{"versao_schema":2}',
            '{"versao_schema":1,"texto":"x","resumo":null,"intencao":null,"parametros_intencao":{},"confianca":1.5,"motivo":"x","requer_confirmacao":false}',
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    parse_resposta_llm(payload)

    def test_sem_intencao_nao_aceita_parametros(self):
        payload = '{"versao_schema":1,"texto":"ok","resumo":null,"intencao":null,"parametros_intencao":{"host":"core"},"confianca":0.8,"motivo":"x","requer_confirmacao":false}'
        with self.assertRaises(ValueError):
            parse_resposta_llm(payload)
