# Workspace local da interface

Este diretório existe apenas para organizar o fluxo local. Copie arquivos do cliente para subdiretórios locais, mas não os adicione ao Git.

Estrutura sugerida:

```text
workspace/
├── baseline-system/       # cópia preservada do System original
├── editing-system/        # cópia utilizada no XDAT_NEW
├── test-system/           # cópia descartável para execução
└── manifests/             # únicos artefatos locais permitidos no Git
```

O `.gitignore` deste diretório bloqueia arquivos binários e pacotes do cliente. Os manifests devem conter hashes e metadados, nunca os bytes proprietários.
