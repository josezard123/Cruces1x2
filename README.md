# Cruces 1-X-2 para Windows

Cada ordenador ejecuta su propia app y su lector. No necesita PulseScore ni depender de otro PC.

## Descargar e instalar

Descarga el instalador de [Releases](https://github.com/josezard123/Cruces1x2/releases/latest), ejecútalo y acepta la instalación. Incluye Python y crea el acceso Cruces en el escritorio. La web local se abre en http://127.0.0.1:8802.

Instala el lector una vez en Chrome o Edge: Extensiones → Modo desarrollador → Cargar descomprimida. Selecciona `%LOCALAPPDATA%\Cruces\lector`. La app muestra la ruta exacta en sus instrucciones. Activa la lectura y abre la web en ese navegador.

## Actualizaciones

La app instalada comprueba las versiones estables al abrirse. En Aplicación y actualizaciones aparece Actualizar aplicación cuando hay una nueva versión. La descarga se comprueba con SHA-256 y tamaño publicados por GitHub antes de ejecutarse. Los ajustes y cuotas se conservan en `%LOCALAPPDATA%\Cruces\datos`, separados del programa.

Si cambia el lector, recárgalo en Extensiones. Su actualización automática requiere publicarlo en una tienda; este paquete utiliza una instalación descomprimida.

## Desarrollo y nuevas versiones

Usa Python 3.12 en Windows. Instala `requirements.txt` y `pyinstaller>=6.20,<7`. Ejecuta `python -m unittest test_distribution` y `python build_windows.py`. Los ejecutables quedan en `distribucion/salida`.

Para cada versión cambia VERSION en runtime_paths.py, realiza las pruebas pertinentes y publica una release estable vVERSION con Cruces-Setup-VERSION.exe, su archivo SHA-256 y el ZIP del lector. Cada copia instalada detectará las futuras releases estables del repositorio.

El paquete incluye solo código y recursos del programa. No incluye claves, ajustes, cuotas ni diagnósticos de otros usuarios.
