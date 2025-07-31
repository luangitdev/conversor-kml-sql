import os
import xml.etree.ElementTree as ET
import re
import sys

def process_kml_file(kml_path):
    # Obtém o nome base do arquivo KML para o nome do arquivo de saída
    base_name = os.path.basename(kml_path)
    output_file_name = f"output_inserts_{os.path.splitext(base_name)[0]}.sql"
    
    # KML parse
    try:
        tree = ET.parse(kml_path)
        root = tree.getroot()
    except Exception as e:
        print(f"Erro ao fazer o parse do arquivo KML {kml_path}: {e}")
        return

    # Especifica o namespace KML
    kml_namespace = "{http://www.opengis.net/kml/2.2}"

    # Cria o arquivo de saída (sobrescreve se já existir)
    with open(output_file_name, 'w') as out_file:
        # Encontra as coordenadas
        placemarks = root.findall(f'.//{kml_namespace}Placemark')
        print(f"Encontrados {len(placemarks)} placemarks no arquivo KML {kml_path}.")

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
            else:
                print("Placemark sem coordenadas. Pulando...")

def main():
    # Verifica se um argumento foi passado
    if len(sys.argv) != 2:
        print("Uso: python3 kmlToSql.py <nome_do_arquivo.kml>")
        return

    # Obtém o caminho do arquivo KML a partir do argumento da linha de comando
    kml_path = sys.argv[1]

    # Verifica se o arquivo existe
    if not os.path.isfile(kml_path):
        print(f"Erro: Arquivo {kml_path} não encontrado.")
        return

    # Processa o arquivo KML
    process_kml_file(kml_path)

if __name__ == '__main__':
    main()
