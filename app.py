from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for
import os
import tempfile
from werkzeug.utils import secure_filename
import shutil
from kmlToSql import process_kml_file, process_directory, get_kml_files_from_directory
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'  # Mude isso para produção

# Configurações
UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'results'
ALLOWED_EXTENSIONS = {'kml'}

# Cria as pastas necessárias
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Verifica se o arquivo tem extensão permitida"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_old_files():
    """Remove arquivos antigos das pastas de upload e resultados"""
    for folder in [UPLOAD_FOLDER, RESULTS_FOLDER]:
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"Erro ao limpar arquivo {file_path}: {e}")

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/upload-single', methods=['POST'])
def upload_single_file():
    """Processa um único arquivo KML"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Nenhum arquivo selecionado'})
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Nenhum arquivo selecionado'})
    
    if file and allowed_file(file.filename):
        # Limpa arquivos antigos
        clean_old_files()
        
        # Salva o arquivo
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        
        try:
            # Processa o arquivo
            # Temporariamente muda o diretório de trabalho para a pasta de resultados
            original_cwd = os.getcwd()
            os.chdir(RESULTS_FOLDER)
            
            success = process_kml_file(os.path.join('..', file_path))
            
            os.chdir(original_cwd)
            
            if success:
                # Encontra o arquivo SQL gerado
                base_name = os.path.splitext(filename)[0]
                sql_filename = f"output_inserts_{base_name}.sql"
                sql_path = os.path.join(RESULTS_FOLDER, sql_filename)
                
                if os.path.exists(sql_path):
                    return jsonify({
                        'success': True, 
                        'message': 'Arquivo processado com sucesso!',
                        'download_url': f'/download/{sql_filename}'
                    })
                else:
                    return jsonify({'success': False, 'error': 'Arquivo SQL não foi gerado'})
            else:
                return jsonify({'success': False, 'error': 'Erro ao processar o arquivo KML'})
                
        except Exception as e:
            os.chdir(original_cwd)  # Garante que volta ao diretório original
            return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'})
    
    return jsonify({'success': False, 'error': 'Tipo de arquivo não permitido'})

@app.route('/upload-multiple', methods=['POST'])
def upload_multiple_files():
    """Processa múltiplos arquivos KML"""
    if 'files[]' not in request.files:
        return jsonify({'success': False, 'error': 'Nenhum arquivo selecionado'})
    
    files = request.files.getlist('files[]')
    
    if not files or all(f.filename == '' for f in files):
        return jsonify({'success': False, 'error': 'Nenhum arquivo selecionado'})
    
    # Limpa arquivos antigos
    clean_old_files()
    
    # Cria pasta temporária para os uploads
    upload_dir = os.path.join(UPLOAD_FOLDER, 'batch')
    os.makedirs(upload_dir, exist_ok=True)
    
    uploaded_files = []
    
    # Salva todos os arquivos
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)
            uploaded_files.append(filename)
    
    if not uploaded_files:
        return jsonify({'success': False, 'error': 'Nenhum arquivo KML válido foi enviado'})
    
    try:
        # Processa os arquivos
        original_cwd = os.getcwd()
        os.chdir(RESULTS_FOLDER)
        
        stats = process_directory(os.path.join('..', upload_dir))
        
        os.chdir(original_cwd)
        
        if stats['success'] > 0:
            # Cria um arquivo SQL consolidado com todos os resultados
            consolidated_filename = 'resultados_kml_consolidado.sql'
            consolidated_path = os.path.join(RESULTS_FOLDER, consolidated_filename)
            
            with open(consolidated_path, 'w', encoding='utf-8') as consolidated_file:
                # Adiciona cabeçalho informativo
                consolidated_file.write("-- ================================================\n")
                consolidated_file.write("-- KML to SQL Converter - Resultados Consolidados\n")
                consolidated_file.write(f"-- Arquivos processados: {stats['success']}\n")
                consolidated_file.write(f"-- Data de geração: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                consolidated_file.write("-- ================================================\n\n")
                
                # Concatena todos os arquivos SQL gerados
                for filename in sorted(os.listdir(RESULTS_FOLDER)):
                    if filename.endswith('.sql') and filename != consolidated_filename:
                        file_path = os.path.join(RESULTS_FOLDER, filename)
                        
                        # Adiciona separador para cada arquivo
                        base_name = filename.replace('output_inserts_', '').replace('.sql', '')
                        consolidated_file.write(f"-- ========== Arquivo: {base_name} ==========\n")
                        
                        with open(file_path, 'r', encoding='utf-8') as sql_file:
                            content = sql_file.read()
                            consolidated_file.write(content)
                            if not content.endswith('\n'):
                                consolidated_file.write('\n')
                        
                        consolidated_file.write(f"-- ========== Fim: {base_name} ==========\n\n")
            
            return jsonify({
                'success': True,
                'message': f'Processamento concluído! {stats["success"]} arquivo(s) processado(s) com sucesso.',
                'stats': stats,
                'download_url': f'/download/{consolidated_filename}'
            })
        else:
            return jsonify({
                'success': False, 
                'error': 'Nenhum arquivo foi processado com sucesso',
                'stats': stats
            })
            
    except Exception as e:
        os.chdir(original_cwd)
        return jsonify({'success': False, 'error': f'Erro interno: {str(e)}'})

@app.route('/download/<filename>')
def download_file(filename):
    """Download do arquivo resultado"""
    file_path = os.path.join(RESULTS_FOLDER, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        flash('Arquivo não encontrado', 'error')
        return redirect(url_for('index'))

@app.route('/api/status')
def api_status():
    """API para verificar status da aplicação"""
    return jsonify({
        'status': 'ok',
        'version': '1.0.0',
        'description': 'KML to SQL Converter Web Interface'
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
