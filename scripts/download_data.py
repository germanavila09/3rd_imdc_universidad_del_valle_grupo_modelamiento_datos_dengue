import os
from ftplib import FTP
from pathlib import Path

def download_challenge_data():
    host = "info.dengue.mat.br"
    remote_dir = "data_imdc_2026"
    local_dir = Path("data")
    
    # Crear la carpeta local de datos si no existe
    local_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Conectando al servidor FTP: {host}...")
    try:
        ftp = FTP(host)
        ftp.login()  # Conexión anónima
        print("Conexión exitosa. Accediendo a la carpeta de datos...")
        
        # Listar archivos
        files = ftp.nlst(remote_dir)
        print(f"Se encontraron {len(files)} archivos para descargar.\n")
        
        for file_path in files:
            # Obtener solo el nombre del archivo (sin la ruta remota si la incluye nlst)
            file_name = os.path.basename(file_path)
            local_file = local_dir / file_name
            
            print(f"Descargando {file_name}...", end="", flush=True)
            
            # Comando para descargar en modo binario
            remote_file_cmd = f"RETR {remote_dir}/{file_name}"
            
            with open(local_file, "wb") as lf:
                ftp.retrbinary(remote_file_cmd, lf.write)
                
            print(" ¡OK!")
            
        ftp.quit()
        print("\n¡Todas las descargas se han completado con éxito!")
        print(f"Los archivos se guardaron en la carpeta: {local_dir.resolve()}")
        
    except Exception as e:
        print(f"\nError durante la descarga: {e}")

if __name__ == "__main__":
    download_challenge_data()
