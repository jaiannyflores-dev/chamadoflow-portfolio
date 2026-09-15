# Política de segurança

## Dados proibidos no repositório

Nunca envie:

- exportações XML, planilhas, contatos ou históricos reais;
- `config.json`, URLs internas, tokens, senhas ou chaves;
- nomes, e-mails, telefones, identificadores de pessoas ou empresas;
- capturas de tela que contenham informações de atendimento.

Use apenas `config.example.json` e dados sintéticos nos testes.

## Antes de cada commit

1. Revise `git status` e `git diff --staged`.
2. Confirme que o `.gitignore` continua cobrindo dados locais.
3. Execute os testes.
4. Procure termos, domínios e identificadores do ambiente de trabalho antes de publicar.

## Relato de vulnerabilidades

Não abra uma issue pública com detalhes de uma vulnerabilidade. Entre em contato com a mantenedora pelo canal privado definido no perfil do GitHub.
