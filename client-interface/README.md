# Ferramentas da interface do cliente

Esta pasta contém somente código, perfis e manifests para trabalhar com a interface do cliente Interlude. Arquivos proprietários do cliente não pertencem ao repositório.

## Conteúdo

- `profiles/interlude-746-l2jtoren.json`: contrato versionado do cliente e da ferramenta;
- `scripts/New-ClientInterfaceManifest.ps1`: inventário SHA-256 e PE do `System`;
- `scripts/validate_profile.py`: valida perfil, manifesto e política de repositório;
- `tests/test_validate_profile.py`: testes unitários sem dependências externas;
- `workspace/`: área local protegida por `.gitignore`.

## Validação rápida

```bash
python tools/client-interface/scripts/validate_profile.py \
  --profile tools/client-interface/profiles/interlude-746-l2jtoren.json

python -m unittest discover \
  -s tools/client-interface/tests \
  -p 'test_*.py' \
  -v
```

## Estado atual

O perfil está em `baseline-pending`. Isso significa que os hashes conhecidos de `Engine.dll` e `Core.dll` estão registrados, mas os hashes do `Interface.xdat` e do `Interface.u` do System oficial ainda precisam ser capturados localmente.
