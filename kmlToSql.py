import os
import xml.etree.ElementTree as ET
import re
import argparse
import glob

def process_kml_file(kml_path):
    """
    Processa um único arquivo KML e gera o arquivo SQL correspondente.
    
    Args:
        kml_path (str): Caminho para o arquivo KML
    
    Returns:
        bool: True se processado com sucesso, False caso contrário
    """
    # Obtém o nome base do arquivo KML para o nome do arquivo de saída
    base_name = os.path.basename(kml_path)
    output_file_name = f"output_inserts_{os.path.splitext(base_name)[0]}.sql"
    
    # KML parse
    try:
        tree = ET.parse(kml_path)
        root = tree.getroot()
    except Exception as e:
        print(f"Erro ao fazer o parse do arquivo KML {kml_path}: {e}")
        return False

    # Especifica o namespace KML
    kml_namespace = "{http://www.opengis.net/kml/2.2}"

    try:
        # Cria o arquivo de saída (sobrescreve se já existir)
        with open(output_file_name, 'w') as out_file:
            success = _process_placemarks(root, kml_namespace, kml_path, out_file)
            
        if success:
            print(f"✅ Arquivo processado com sucesso: {output_file_name}")
            return True
        else:
            print(f"⚠️ Arquivo processado com avisos: {output_file_name}")
            return True
            
    except Exception as e:
        print(f"❌ Erro ao escrever arquivo de saída {output_file_name}: {e}")
        return False

def _process_placemarks(root, kml_namespace, kml_path, out_file):
    """
    Processa todos os placemarks de um arquivo KML.
    
    Args:
        root: Elemento raiz do XML
        kml_namespace (str): Namespace do KML
        kml_path (str): Caminho do arquivo KML (para logs)
        out_file: Handle do arquivo de saída
    
    Returns:
        bool: True se pelo menos um placemark foi processado
    """
    # Encontra as coordenadas
    placemarks = root.findall(f'.//{kml_namespace}Placemark')
    print(f"Encontrados {len(placemarks)} placemarks no arquivo KML {kml_path}.")
    
    processed_count = 0

    for index, placemark in enumerate(placemarks, start=1):
        print(f"Processando Placemark {index}/{len(placemarks)} do arquivo {kml_path}")

        # Extrai o nome
        name_element = placemark.find(f'.//{kml_namespace}SimpleData[@name="layer"]')
        if name_element is not None:
            name = name_element.text
            print(f"Nome: {name}")
        else:
            print("Placemark sem nome. Pulando...")
            continue  # Ignora marcadores sem nome

        # Extrai a camada
        layer_element = placemark.find(f".//{kml_namespace}SimpleData[@name='layer']")
        if layer_element is not None:
            layer = layer_element.text
            print(f"Layer: {layer}")
        else:
            print("Placemark sem camada. Pulando...")
            continue  # Ignora marcadores sem camada

        # Extrai coordenadas
        coordinates_element = placemark.find(f'.//{kml_namespace}coordinates')
        if coordinates_element is not None:
            coordinates = coordinates_element.text.strip()
            coordinates = re.findall(r'(-?\d+\.\d+),(-?\d+\.\d+)', coordinates)

            # Escreve o insert da zona no arquivo de saída
            out_file.write(f"INSERT INTO zona (custofixo, custoporentrega, nome, restrita, utilizaexpediente, utilizapernoite, agrupavel, tipo_solucao, sequencia, tipo_zona) "
                           f"SELECT 0, 0, '{layer}', 'true', 'false', 'false', 'false', 'TODAS', 99999, 'SIMULACAO' WHERE NOT EXISTS "
                           f"(SELECT 1 FROM zona WHERE nome = '{layer}');\n")

            # Escreve os inserts das coordenadas no arquivo de saída
            for (lat, lon) in coordinates:
                print(f"Insert gerado para {name}, {layer}, Lat: {lon}, Lon: {lat}")
                out_file.write(f"INSERT INTO coordenada(latitude, longitude, id_zona) "
                               f"VALUES({lon}, {lat}, (SELECT id FROM zona WHERE nome = '{layer}'));\n")
            
            processed_count += 1
        else:
            print("Placemark sem coordenadas. Pulando...")
    
    return processed_count > 0

def get_kml_files_from_directory(directory_path):
    """
    Obtém todos os arquivos KML de um diretório.
    
    Args:
        directory_path (str): Caminho do diretório
    
    Returns:
        list: Lista de caminhos para arquivos KML
    """
    if not os.path.isdir(directory_path):
        print(f"❌ Erro: Diretório {directory_path} não encontrado.")
        return []
    
    kml_files = glob.glob(os.path.join(directory_path, "*.kml"))
    
    if not kml_files:
        print(f"⚠️ Nenhum arquivo KML encontrado no diretório {directory_path}")
        return []
    
    print(f"📁 Encontrados {len(kml_files)} arquivos KML no diretório {directory_path}")
    return sorted(kml_files)

def process_directory(directory_path):
    """
    Processa todos os arquivos KML em um diretório.
    
    Args:
        directory_path (str): Caminho do diretório
    
    Returns:
        dict: Estatísticas do processamento
    """
    kml_files = get_kml_files_from_directory(directory_path)
    
    if not kml_files:
        return {"total": 0, "success": 0, "errors": 0}
    
    stats = {"total": len(kml_files), "success": 0, "errors": 0}
    
    print(f"\n🚀 Iniciando processamento de {len(kml_files)} arquivos...\n")
    
    for i, kml_file in enumerate(kml_files, 1):
        print(f"📄 [{i}/{len(kml_files)}] Processando: {os.path.basename(kml_file)}")
        
        if process_kml_file(kml_file):
            stats["success"] += 1
        else:
            stats["errors"] += 1
        
        print("-" * 50)
    
    return stats

def print_summary(stats):
    """
    Imprime um resumo das estatísticas de processamento.
    
    Args:
        stats (dict): Dicionário com estatísticas
    """
    print("\n" + "=" * 50)
    print("📊 RESUMO DO PROCESSAMENTO")
    print("=" * 50)
    print(f"Total de arquivos: {stats['total']}")
    print(f"✅ Processados com sucesso: {stats['success']}")
    print(f"❌ Erros: {stats['errors']}")
    
    if stats['total'] > 0:
        success_rate = (stats['success'] / stats['total']) * 100
        print(f"📈 Taxa de sucesso: {success_rate:.1f}%")

def create_argument_parser():
    """
    Cria e configura o parser de argumentos.
    
    Returns:
        argparse.ArgumentParser: Parser configurado
    """
    parser = argparse.ArgumentParser(
        description="Converte arquivos KML para comandos SQL INSERT",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python3 kmlToSql.py -f arquivo.kml           # Processa um arquivo específico
  python3 kmlToSql.py -d /caminho/para/pasta   # Processa todos os KMLs da pasta
  python3 kmlToSql.py -d .                     # Processa todos os KMLs da pasta atual
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-f", "--file",
        type=str,
        help="Processa um arquivo KML específico"
    )
    group.add_argument(
        "-d", "--directory",
        type=str,
        help="Processa todos os arquivos KML de um diretório"
    )
    
    return parser

def main():
    """
    Função principal do programa.
    """
    parser = create_argument_parser()
    args = parser.parse_args()
    
    if args.file:
        # Modo arquivo único
        if not os.path.isfile(args.file):
            print(f"❌ Erro: Arquivo {args.file} não encontrado.")
            return 1
        
        if not args.file.lower().endswith('.kml'):
            print(f"⚠️ Aviso: O arquivo {args.file} não possui extensão .kml")
        
        print(f"📄 Processando arquivo único: {args.file}")
        success = process_kml_file(args.file)
        return 0 if success else 1
    
    elif args.directory:
        # Modo diretório
        print(f"📁 Processando diretório: {args.directory}")
        stats = process_directory(args.directory)
        print_summary(stats)
        return 0 if stats["errors"] == 0 else 1

if __name__ == '__main__':
    exit(main())