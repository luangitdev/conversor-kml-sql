# KML to SQL Converter - Interface Web

Aplicação web para converter arquivos KML em comandos SQL INSERT, com interface gráfica amigável desenvolvida em Flask + Bootstrap.

## 🚀 Executando com Docker

### Pré-requisitos
- Docker
- Docker Compose

### Opção 1: Usando Docker Compose (Recomendado)

```bash
# Clone o repositório (se necessário)
git clone <seu-repositorio>
cd kml-to-sql-new

# Construir e executar o container
docker-compose up -d

# Para ver os logs
docker-compose logs -f

# Para parar a aplicação
docker-compose down
```

A aplicação estará disponível em: **http://localhost:5000**

### Opção 2: Usando Docker diretamente

```bash
# Construir a imagem
docker build -t kml-to-sql-converter .

# Executar o container
docker run -d \
  --name kml-converter \
  -p 5000:5000 \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/results:/app/results \
  kml-to-sql-converter

# Para ver os logs
docker logs -f kml-converter

# Para parar o container
docker stop kml-converter
docker rm kml-converter
```

## 🎯 Como Usar

1. **Acesse** http://localhost:5000 no seu navegador
2. **Escolha uma das opções**:
   - **Arquivo Único**: Para converter um arquivo KML individual
   - **Múltiplos Arquivos**: Para processar vários arquivos em lote
3. **Arraste ou selecione** seus arquivos KML
4. **Clique em "Converter para SQL"**
5. **Baixe** o(s) arquivo(s) SQL gerado(s)

## 📁 Estrutura de Arquivos

```
kml-to-sql-new/
├── app.py                 # Aplicação Flask principal
├── kmlToSql.py           # Lógica original de conversão
├── templates/
│   └── index.html        # Interface web
├── static/               # Arquivos estáticos (CSS, JS)
├── uploads/              # Arquivos KML enviados
├── results/              # Arquivos SQL gerados
├── Dockerfile            # Configuração do container
├── docker-compose.yml    # Orquestração Docker
├── requirements.txt      # Dependências Python
├── start.sh             # Script de inicialização
└── README.md            # Este arquivo
```

## 🔧 Funcionalidades

### Conversão de Arquivos
- ✅ **Arquivo único**: Converte um arquivo KML individual
- ✅ **Processamento em lote**: Múltiplos arquivos KML de uma vez
- ✅ **Download automático**: Arquivos SQL prontos para download
- ✅ **Validação inteligente**: Detecta problemas nos arquivos KML

### Formatos Suportados
- ✅ `Data[@name='zona']` - Campo zona personalizado
- ✅ `SimpleData[@name='layer']` - Camadas simples
- ✅ `description` - Descrições padrão
- ✅ `Data[@name='Description']` - Formato Google Earth
- ✅ `Data[@name='Name']` - Nomes do Google Earth

### Interface Web
- ✅ **Drag & Drop**: Arraste arquivos diretamente
- ✅ **Responsivo**: Funciona em desktop e mobile
- ✅ **Bootstrap 5**: Interface moderna e intuitiva
- ✅ **Feedback visual**: Progresso e status em tempo real

## 🐳 Comandos Docker Úteis

```bash
# Ver status dos containers
docker-compose ps

# Reconstruir a imagem (após mudanças no código)
docker-compose build

# Reiniciar a aplicação
docker-compose restart

# Ver logs em tempo real
docker-compose logs -f

# Entrar no container (para debug)
docker-compose exec kml-to-sql-web bash

# Limpar volumes e containers
docker-compose down -v
docker system prune -a
```

## 🔒 Segurança

- Container executa com usuário não-privilegiado
- Arquivos temporários são limpos automaticamente
- Validação de tipos de arquivo
- Sanitização de nomes de arquivo

## 📊 Monitoramento

A aplicação inclui um endpoint de status para monitoramento:

```bash
curl http://localhost:5000/api/status
```

Resposta:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "description": "KML to SQL Converter Web Interface"
}
```

## 🛠️ Desenvolvimento

Para executar em modo de desenvolvimento:

```bash
# Instalar dependências
pip install -r requirements.txt

# Executar em modo debug
export FLASK_ENV=development
python app.py
```

## 📝 Notas

- Os arquivos de upload são automaticamente limpos a cada nova conversão
- Resultados ficam disponíveis na pasta `results/`
- Para uso em produção, configure variáveis de ambiente apropriadas
- O container usa Gunicorn para melhor performance em produção

## 🆘 Troubleshooting

### Container não inicia
```bash
# Verificar logs
docker-compose logs

# Reconstruir imagem
docker-compose build --no-cache
```

### Permissões de arquivo
```bash
# Ajustar permissões das pastas
sudo chown -R $USER:$USER uploads results
chmod 755 uploads results
```

### Porta em uso
Se a porta 5000 estiver ocupada, edite o `docker-compose.yml`:
```yaml
ports:
  - "8080:5000"  # Muda para porta 8080
```
