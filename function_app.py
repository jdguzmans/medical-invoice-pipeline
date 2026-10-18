import azure.functions as func
import logging
import os
from azure.storage.blob import BlobServiceClient

app = func.FunctionApp()

@app.route(route="EnrutadorFacturas", auth_level=func.AuthLevel.FUNCTION)
def EnrutadorFacturas(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Iniciando validación y ruteo de factura...')
    
    try:
        req_body = req.get_json()
        file_name = req_body.get('file_name')
    except ValueError:
        return func.HttpResponse("JSON inválido", status_code=400)

    if not file_name:
        return func.HttpResponse("Falta el file_name en el cuerpo de la solicitud", status_code=400)

    # Configuración de conexión al Storage Account
    connection_string = os.environ["AzureWebJobsStorage"]
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_name = "facturacion-medica"
    
    # El archivo origen ahora está en la carpeta "Crudo"
    source_blob_name = f"Crudo/{file_name}"
    source_blob = blob_service_client.get_blob_client(container=container_name, blob=source_blob_name)
    
    if not source_blob.exists():
        return func.HttpResponse(f"El archivo {file_name} no se encontró en Crudo", status_code=404)

    # 1. Validación de duplicados
    destinos = ["Flujo_actual", "Flujo_nuevo", "Duplicados"]
    es_duplicado = False
    
    for dest in destinos:
        check_blob = blob_service_client.get_blob_client(container=container_name, blob=f"{dest}/{file_name}")
        if check_blob.exists():
            es_duplicado = True
            break
            
    # 2. Lógica de ruteo
    if es_duplicado:
        destino_folder = "Duplicados"
        logging.info(f"Factura duplicada detectada. Enrutando a {destino_folder}")
    else:
        # Contar archivos procesados previamente para la regla exacta de 1 de cada 5
        container_client = blob_service_client.get_container_client(container_name)
        
        # Listamos los archivos en las carpetas destino (ignorando el placeholder.txt que usamos para crearlas)
        blobs_actual = [b.name for b in container_client.list_blobs(name_starts_with="Flujo_actual/") if not b.name.endswith('placeholder.txt')]
        blobs_nuevo = [b.name for b in container_client.list_blobs(name_starts_with="Flujo_nuevo/") if not b.name.endswith('placeholder.txt')]
        
        total_procesados = len(blobs_actual) + len(blobs_nuevo)
        
        # Matemática determinista: si el conteo es 0, 5, 10, 15... va al flujo nuevo.
        if total_procesados % 5 == 0:
            destino_folder = "Flujo_nuevo"
        else:
            destino_folder = "Flujo_actual"
            
        logging.info(f"Factura nueva. Total previas: {total_procesados}. Enrutando a {destino_folder}")
            
    # 3. Ejecutar la copia del archivo
    dest_blob_name = f"{destino_folder}/{file_name}"
    dest_blob = blob_service_client.get_blob_client(container=container_name, blob=dest_blob_name)
    
    dest_blob.start_copy_from_url(source_blob.url)
    
    # Hemos eliminado la instrucción source_blob.delete_blob() 
    # El archivo original permanecerá intacto en la carpeta "Crudo".
    
    return func.HttpResponse(f"Archivo {file_name} copiado a {destino_folder} y mantenido en Crudo", status_code=200)