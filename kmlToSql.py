import os
import xml.etree.ElementTree as ET
import re
import argparse
import glob
import math

DEFAULT_SIMPLIFICATION_TOLERANCE = 0.0001


def _get_simplification_tolerance():
    """
    Obtém a tolerância de simplificação das coordenadas.

    A unidade é grau decimal. O padrão 0.0001 equivale a aproximadamente 11m
    em latitude, reduzindo pontos redundantes sem deformar muito a geometria.
    """
    raw_value = os.getenv("KML_SIMPLIFY_TOLERANCE")
    if not raw_value:
        return DEFAULT_SIMPLIFICATION_TOLERANCE

    try:
        tolerance = float(raw_value)
        if tolerance < 0:
            raise ValueError
        return tolerance
    except ValueError:
        print(
            "⚠️ Valor inválido em KML_SIMPLIFY_TOLERANCE. "
            f"Usando padrão {DEFAULT_SIMPLIFICATION_TOLERANCE}."
        )
        return DEFAULT_SIMPLIFICATION_TOLERANCE


def _perpendicular_distance(point, start, end):
    """
    Calcula a distância perpendicular de um ponto a uma reta.

    Os pontos são tuplas no formato (longitude, latitude).
    """
    if start == end:
        return math.hypot(point[0] - start[0], point[1] - start[1])

    numerator = abs(
        (end[0] - start[0]) * (start[1] - point[1])
        - (start[0] - point[0]) * (end[1] - start[1])
    )
    denominator = math.hypot(end[0] - start[0], end[1] - start[1])
    return numerator / denominator


def _ramer_douglas_peucker(points, tolerance):
    """
    Simplifica uma sequência de pontos com Ramer-Douglas-Peucker.
    """
    if len(points) <= 2:
        return points[:]

    max_distance = 0.0
    farthest_index = 0

    for index in range(1, len(points) - 1):
        distance = _perpendicular_distance(points[index], points[0], points[-1])
        if distance > max_distance:
            max_distance = distance
            farthest_index = index

    if max_distance > tolerance:
        left = _ramer_douglas_peucker(points[:farthest_index + 1], tolerance)
        right = _ramer_douglas_peucker(points[farthest_index:], tolerance)
        return left[:-1] + right

    return [points[0], points[-1]]


def _simplify_coordinates(coordinates, tolerance=None):
    """
    Reduz pontos redundantes mantendo o desenho geral da geometria.

    Se a sequência vier fechada (primeiro ponto igual ao último), ela é
    simplificada sem o ponto duplicado e fechada novamente no final.
    """
    if tolerance is None:
        tolerance = _get_simplification_tolerance()

    if tolerance <= 0 or len(coordinates) <= 2:
        return coordinates[:]

    is_closed = len(coordinates) > 2 and coordinates[0] == coordinates[-1]
    points_to_simplify = coordinates[:-1] if is_closed else coordinates

    minimum_points = 3 if is_closed else 2
    if len(points_to_simplify) <= minimum_points:
        return coordinates[:]

    simplified = _ramer_douglas_peucker(points_to_simplify, tolerance)

    if is_closed:
        if len(simplified) < 3:
            simplified = points_to_simplify[:3]
        if simplified[0] != simplified[-1]:
            simplified.append(simplified[0])

    return simplified

TRUNCATED_KML_SUFFIXES = ("</Document></kml>", "</kml>", "</Document>")


def _parse_kml(kml_path):
    """
    Faz o parse de um KML, tolerando arquivo truncado.

    Se o XML estiver incompleto, tenta fechar as tags finais (Document/kml)
    em memória, sem alterar o arquivo. Se nenhuma tentativa funcionar, relança
    o erro original do parse.

    Returns:
        Element: elemento raiz do XML
    """
    try:
        return ET.parse(kml_path).getroot()
    except ET.ParseError as original_error:
        with open(kml_path, encoding="utf-8", errors="replace") as kml_file:
            content = kml_file.read().rstrip()

        for suffix in TRUNCATED_KML_SUFFIXES:
            try:
                root = ET.fromstring(content + suffix)
            except ET.ParseError:
                continue
            print(
                f"⚠️ KML truncado em {kml_path}: tags finais ausentes, "
                f"fechadas automaticamente com '{suffix}'. "
                "Confirme com o cliente se o arquivo não perdeu Placemarks."
            )
            return root

        raise original_error


def process_kml_file(kml_path, planner=False):
    """
    Processa um único arquivo KML e gera o arquivo SQL correspondente.
    
    Args:
        kml_path (str): Caminho para o arquivo KML
        planner (bool): Gera os inserts no formato Planner
    
    Returns:
        bool: True se processado com sucesso, False caso contrário
    """
    # Obtém o nome base do arquivo KML para o nome do arquivo de saída
    base_name = os.path.basename(kml_path)
    output_file_name = f"output_inserts_{os.path.splitext(base_name)[0]}.sql"
    
    # KML parse
    try:
        root = _parse_kml(kml_path)
    except Exception as e:
        print(f"Erro ao fazer o parse do arquivo KML {kml_path}: {e}")
        return False

    # Especifica o namespace KML
    kml_namespace = "{http://www.opengis.net/kml/2.2}"

    try:
        # Cria o arquivo de saída (sobrescreve se já existir)
        with open(output_file_name, 'w') as out_file:
            success = _process_placemarks(root, kml_namespace, kml_path, out_file, planner)
            
        if success:
            print(f"✅ Arquivo processado com sucesso: {output_file_name}")
            return True
        else:
            print(f"❌ Erro: Nenhum placemark válido encontrado no arquivo {kml_path}")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao escrever arquivo de saída {output_file_name}: {e}")
        return False

def _extract_layer_name(placemark, kml_namespace):
    """
    Extrai o nome da camada de um placemark, buscando em SimpleData, description ou Data.
    
    Args:
        placemark: Elemento placemark do XML
        kml_namespace (str): Namespace do KML
    
    Returns:
        str or None: Nome da camada encontrado ou None se não encontrar
    """
    # Prioridade 1: Busca em Data[@name='zona'] (formato específico do usuário)
    data_zona = placemark.find(f".//{kml_namespace}Data[@name='zona']/{kml_namespace}value")
    if data_zona is not None and data_zona.text:
        return data_zona.text.strip()
    
    # Prioridade 2: Busca em SimpleData[@name='layer']
    layer_element = placemark.find(f".//{kml_namespace}SimpleData[@name='layer']")
    if layer_element is not None and layer_element.text:
        return layer_element.text.strip()
    
    # Prioridade 3: Busca em description
    description_element = placemark.find(f".//{kml_namespace}description")
    if description_element is not None and description_element.text:
        description_text = description_element.text.strip()
        # Remove possível sufixo " / UF" (ex: "JUAZEIRO DO NORTE / CE" -> "JUAZEIRO DO NORTE")
        if ' / ' in description_text:
            return description_text.split(' / ')[0].strip()
        return description_text
    
    # Prioridade 4: Busca em Data[@name='Description'] (formato Google Earth)
    data_description = placemark.find(f".//{kml_namespace}Data[@name='Description']/{kml_namespace}value")
    if data_description is not None and data_description.text:
        description_text = data_description.text.strip()
        # Remove possível sufixo " / UF" (ex: "ACOPIARA / CE" -> "ACOPIARA")
        if ' / ' in description_text:
            return description_text.split(' / ')[0].strip()
        return description_text
    
    # Prioridade 5: Busca em Data[@name='Name'] (formato Google Earth) - case-insensitive
    # Tenta diferentes variações de case; NM_UF é o formato IBGE (nome da UF)
    for name_attr in ['Name', 'NAME', 'name', 'NM_UF']:
        data_name = placemark.find(f".//{kml_namespace}Data[@name='{name_attr}']/{kml_namespace}value")
        if data_name is not None and data_name.text:
            return data_name.text.strip()

    # Prioridade 6: Busca em <name> do próprio Placemark (formato Google Earth / regioes_v9)
    name_element = placemark.find(f"{kml_namespace}name")
    if name_element is not None and name_element.text:
        name_text = name_element.text.strip()
        # Remove prefixo "Zona: " se existir (ex: "Zona: CAMPO_MOURAO" -> "CAMPO_MOURAO")
        if name_text.lower().startswith("zona:"):
            return name_text[5:].strip()
        return name_text

    return None

def _validate_kml_structure(root, kml_namespace, kml_path):
    """
    Valida a estrutura do arquivo KML e identifica possíveis problemas.
    
    Args:
        root: Elemento raiz do XML
        kml_namespace (str): Namespace do KML
        kml_path (str): Caminho do arquivo KML (para logs)
    
    Returns:
        dict: {"valid": bool, "warnings": list, "errors": list}
    """
    validation_result = {"valid": True, "warnings": [], "errors": []}
    
    # Encontra todos os placemarks
    placemarks = root.findall(f'.//{kml_namespace}Placemark')
    
    if len(placemarks) == 0:
        validation_result["errors"].append("Nenhum Placemark encontrado no arquivo")
        validation_result["valid"] = False
        return validation_result
    
    for index, placemark in enumerate(placemarks, start=1):
        placemark_issues = []
        
        # Verifica ExtendedData
        extended_data = placemark.find(f'.//{kml_namespace}ExtendedData')
        if extended_data is not None:
            # Verifica se ExtendedData está bem formado
            data_elements = extended_data.findall(f'.//{kml_namespace}Data')
            if len(data_elements) == 0:
                placemark_issues.append("ExtendedData vazio ou malformado")
            else:
                # Verifica se os Data elements têm value
                for data_elem in data_elements:
                    name_attr = data_elem.get('name')
                    value_elem = data_elem.find(f'{kml_namespace}value')
                    if name_attr and value_elem is None:
                        placemark_issues.append(f"Data[@name='{name_attr}'] sem elemento <value>")
                    elif name_attr and value_elem is not None and not value_elem.text:
                        placemark_issues.append(f"Data[@name='{name_attr}'] com <value> vazio")
        
        # Verifica se tem layer identificável
        layer = _extract_layer_name(placemark, kml_namespace)
        if not layer:
            placemark_issues.append("Nenhum layer/nome identificável encontrado")
        
        # Verifica coordenadas
        coordinates_element = placemark.find(f'.//{kml_namespace}coordinates')
        if coordinates_element is None:
            placemark_issues.append("Elemento <coordinates> não encontrado")
        elif not coordinates_element.text or not coordinates_element.text.strip():
            placemark_issues.append("Elemento <coordinates> vazio")
        else:
            # Valida formato das coordenadas
            coords_text = coordinates_element.text.strip()
            coord_matches = re.findall(r'(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)', coords_text)
            if len(coord_matches) == 0:
                placemark_issues.append("Nenhuma coordenada válida encontrada")
        
        # Verifica estrutura XML do placemark - aceita LineString, Polygon, Point ou MultiGeometry
        has_geometry = (
            placemark.find(f'.//{kml_namespace}LineString') is not None or
            placemark.find(f'.//{kml_namespace}Polygon') is not None or
            placemark.find(f'.//{kml_namespace}Point') is not None or
            placemark.find(f'.//{kml_namespace}MultiGeometry') is not None
        )
        if not has_geometry:
            placemark_issues.append("Nenhum elemento de geometria válido encontrado (LineString, Polygon, Point ou MultiGeometry)")
        
        # Se há problemas, adiciona aos avisos/erros
        if placemark_issues:
            if layer:  # Se conseguiu extrair layer, é aviso
                validation_result["warnings"].append(f"Placemark {index} ('{layer}'): {', '.join(placemark_issues)}")
            else:  # Sem layer é erro mais grave
                validation_result["errors"].append(f"Placemark {index}: {', '.join(placemark_issues)}")
                validation_result["valid"] = False
    
    return validation_result

def _parse_coordinates_text(text):
    """
    Converte o texto de uma tag <coordinates> em lista de tuplas (longitude, latitude).
    """
    return [
        (float(lon), float(lat))
        for lon, lat in re.findall(r'(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)', text)
    ]


def _extract_coordinates(placemark, kml_namespace):
    """
    Extrai coordenadas de um Placemark, suportando LineString, Polygon e MultiGeometry.
    Ignora Point pois são apenas marcações de referência, não zonas.

    Quando o Placemark tem mais de uma geometria (ex: MultiGeometry com
    continente + ilhas), mantém apenas a maior (por número de pontos) para não
    gerar linhas falsas ligando o fim de uma geometria ao início da outra.
    As descartadas são informadas no log.

    Args:
        placemark: Elemento placemark do XML
        kml_namespace (str): Namespace do KML

    Returns:
        list: Lista de tuplas (longitude, latitude)
    """
    candidates = []

    for linestring in placemark.iter(f'{kml_namespace}LineString'):
        coords_elem = linestring.find(f'{kml_namespace}coordinates')
        if coords_elem is not None and coords_elem.text:
            candidates.append(_parse_coordinates_text(coords_elem.text))

    for polygon in placemark.iter(f'{kml_namespace}Polygon'):
        coords_elem = polygon.find(
            f'{kml_namespace}outerBoundaryIs/{kml_namespace}LinearRing/{kml_namespace}coordinates'
        )
        if coords_elem is not None and coords_elem.text:
            candidates.append(_parse_coordinates_text(coords_elem.text))

    candidates = [coords for coords in candidates if coords]
    if not candidates:
        return []

    if len(candidates) == 1:
        return candidates[0]

    largest = max(candidates, key=len)
    discarded_sizes = sorted(
        (len(coords) for coords in candidates if coords is not largest),
        reverse=True,
    )
    print(
        f"⚠️ Placemark com {len(candidates)} geometrias: mantida a maior "
        f"({len(largest)} pts), descartadas {len(discarded_sizes)} "
        f"({', '.join(f'{size} pts' for size in discarded_sizes)})"
    )
    return largest

def _process_placemarks(root, kml_namespace, kml_path, out_file, planner=False):
    """
    Processa todos os placemarks de um arquivo KML.
    
    Args:
        root: Elemento raiz do XML
        kml_namespace (str): Namespace do KML
        kml_path (str): Caminho do arquivo KML (para logs)
        out_file: Handle do arquivo de saída
        planner (bool): Gera os inserts no formato Planner
    
    Returns:
        bool: True se pelo menos um placemark foi processado
    """
    # Valida a estrutura do arquivo primeiro
    validation = _validate_kml_structure(root, kml_namespace, kml_path)
    
    # Exibe avisos se houver
    if validation["warnings"]:
        print("⚠️ Avisos encontrados no arquivo:")
        for warning in validation["warnings"]:
            print(f"   {warning}")
    
    # Exibe erros se houver
    if validation["errors"]:
        print("❌ Erros encontrados no arquivo:")
        for error in validation["errors"]:
            print(f"   {error}")
        print("💡 Dica: Verifique se todas as tags XML estão fechadas corretamente")
    
    # Encontra as coordenadas
    placemarks = root.findall(f'.//{kml_namespace}Placemark')
    print(f"Encontrados {len(placemarks)} placemarks no arquivo KML {kml_path}.")
    
    processed_count = 0

    for index, placemark in enumerate(placemarks, start=1):
        print(f"Processando Placemark {index}/{len(placemarks)} do arquivo {kml_path}")

        # Extrai o nome da camada usando a função auxiliar
        layer = _extract_layer_name(placemark, kml_namespace)
        if layer:
            print(f"Layer encontrado: {layer}")
        else:
            print("Placemark sem camada válida. Pulando...")
            continue

        # Usa o layer como nome também (compatibilidade com código anterior)
        name = layer

        # Extrai coordenadas
        coordinates = _extract_coordinates(placemark, kml_namespace)

        if not coordinates:
            print("Placemark sem coordenadas válidas. Pulando...")
            continue

        original_point_count = len(coordinates)
        coordinates = _simplify_coordinates(coordinates)
        removed_point_count = original_point_count - len(coordinates)
        print(
            f"Simplificação de pontos: {original_point_count} -> {len(coordinates)} "
            f"({removed_point_count} removidos)"
        )

        # Escreve o insert da zona no arquivo de saída
        if planner:
            out_file.write(f"INSERT INTO zona (ativo, estimativadepeso, nome, peso_maximo, quantidadedeclientes, semanaentrega, diaentrega) "
                           f"SELECT 'true', 0, '{layer}', 9999999, 0, '-----', 'NNNNNNN' WHERE NOT EXISTS "
                           f"(SELECT 1 FROM zona WHERE nome = '{layer}');\n")
            coordenada_insert = "INSERT INTO coordenada(latitude, longitude, zona_id) "
        else:
            out_file.write(f"INSERT INTO zona (custofixo, custoporentrega, nome, restrita, utilizaexpediente, utilizapernoite, agrupavel, tipo_solucao, sequencia, tipo_zona) "
                           f"SELECT 0, 0, '{layer}', 'true', 'false', 'false', 'false', 'TODAS', 99999, 'SIMULACAO' WHERE NOT EXISTS "
                           f"(SELECT 1 FROM zona WHERE nome = '{layer}');\n")
            coordenada_insert = "INSERT INTO coordenada(latitude, longitude, id_zona) "

        # Escreve os inserts das coordenada no arquivo de saída
        for longitude, latitude in coordinates:
            print(f"Insert gerado para {name}, {layer}, Lat: {latitude}, Lon: {longitude}")
            out_file.write(f"{coordenada_insert}"
                           f"VALUES({latitude}, {longitude}, (SELECT id FROM zona WHERE nome = '{layer}'));\n")

        processed_count += 1
    
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

def process_directory(directory_path, planner=False):
    """
    Processa todos os arquivos KML em um diretório.
    
    Args:
        directory_path (str): Caminho do diretório
        planner (bool): Gera os inserts no formato Planner
    
    Returns:
        dict: Estatísticas do processamento
    """
    kml_files = get_kml_files_from_directory(directory_path)
    
    if not kml_files:
        return {"total": 0, "success": 0, "errors": 0, "no_valid_layers": 0}
    
    stats = {"total": len(kml_files), "success": 0, "errors": 0, "no_valid_layers": 0}
    
    print(f"\n🚀 Iniciando processamento de {len(kml_files)} arquivos...\n")
    
    for i, kml_file in enumerate(kml_files, 1):
        print(f"📄 [{i}/{len(kml_files)}] Processando: {os.path.basename(kml_file)}")
        
        result = process_kml_file(kml_file, planner)
        if result:
            stats["success"] += 1
        else:
            # Se process_kml_file retornou False, pode ser erro de parsing ou sem layers válidos
            # Vamos verificar qual foi a causa real
            try:
                root = _parse_kml(kml_file)
                kml_namespace = "{http://www.opengis.net/kml/2.2}"
                placemarks = root.findall(f'.//{kml_namespace}Placemark')
                
                if len(placemarks) > 0:
                    # Arquivo válido mas sem layers válidos (já foi detectado em process_kml_file)
                    stats["no_valid_layers"] += 1
                    print(f"⚠️ Arquivo {os.path.basename(kml_file)}: Nenhum layer válido encontrado")
                else:
                    # Arquivo válido mas sem placemarks
                    stats["errors"] += 1
                    print(f"❌ Arquivo {os.path.basename(kml_file)}: Sem placemarks válidos")
            except Exception as parse_error:
                # Erro real de parsing XML
                stats["errors"] += 1
                print(f"❌ Arquivo {os.path.basename(kml_file)}: Erro de parsing XML - {str(parse_error)}")
        
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
    print(f"⚠️ Sem layers válidos: {stats['no_valid_layers']}")
    print(f"❌ Erros de parsing: {stats['errors']}")
    
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
    
    parser.add_argument(
        "--planner",
        action="store_true",
        help="Gera os inserts no formato Planner"
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
        success = process_kml_file(args.file, args.planner)
        return 0 if success else 1
    
    elif args.directory:
        # Modo diretório
        print(f"📁 Processando diretório: {args.directory}")
        stats = process_directory(args.directory, args.planner)
        print_summary(stats)
        return 0 if (stats["errors"] + stats["no_valid_layers"]) == 0 else 1

if __name__ == '__main__':
    exit(main())
