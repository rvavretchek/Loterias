#!/bin/bash
# Deploy script para atualizar a aplicação Loterias
# Uso: bash /opt/loterias/deploy.sh
set -e

cd /opt/loterias
echo "📥 Atualizando código..."
git pull origin main

echo "📦 Instalando dependências..."
source .venv/bin/activate
pip install -r requirements.txt

echo "🗄️  Migrando banco de dados..."
python manage.py migrate --noinput

echo "📁 Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

echo "🔄 Reiniciando aplicação..."
sudo systemctl restart loterias

echo ""
echo "✅ Deploy concluído com sucesso!"
echo "   Acesse: http://loterias.integrit.lab"
