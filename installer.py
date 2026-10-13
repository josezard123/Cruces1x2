"""Per-user install; replaces program files without touching user data."""
import argparse
import ctypes
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

def install(payload, root):
    binary_dir = Path(root) / 'programa'
    binary_dir.mkdir(parents=True, exist_ok=True)
    source = Path(payload) / 'Cruces.exe'
    expected = (Path(payload) / 'Cruces.sha256').read_text().strip()
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
        raise ValueError('El programa no supera la verificación.')
    destination = binary_dir / 'Cruces.exe'
    temporary = binary_dir / 'Cruces.new'
    previous = binary_dir / 'Cruces.anterior.exe'
    shutil.copyfile(source, temporary)
    try:
        if destination.exists():
            previous.unlink(missing_ok=True)
            destination.replace(previous)
        temporary.replace(destination)
    except Exception:
        if not destination.exists() and previous.exists():
            previous.replace(destination)
        raise
    finally:
        temporary.unlink(missing_ok=True)
    return destination

def shortcut(executable):
    quote = lambda s: "'" + str(s).replace("'", "''") + "'"
    script = "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'Cruces.lnk'));$s.TargetPath="+quote(executable)+";$s.WorkingDirectory="+quote(executable.parent)+";$s.Save()"
    subprocess.run(['powershell.exe', '-NoProfile', '-Command', script], check=True, creationflags=subprocess.CREATE_NO_WINDOW)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--update', action='store_true')
    parser.add_argument('--parent-pid', type=int)
    parser.add_argument('--test-root')
    parser.add_argument('--no-launch', action='store_true')
    args = parser.parse_args()
    if not args.test_root and not args.update:
        if ctypes.windll.user32.MessageBoxW(None, 'Instalar Cruces para este usuario de Windows y crear un acceso en el escritorio. No necesitas instalar Python.', 'Instalar Cruces', 1) != 1:
            return
    if args.parent_pid:
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x100000, False, args.parent_pid)
        if handle:
            try:
                if kernel.WaitForSingleObject(handle, 45000) != 0:
                    raise RuntimeError('Cierra Cruces para actualizarla.')
            finally:
                kernel.CloseHandle(handle)
    root = Path(args.test_root) if args.test_root else Path(os.environ['LOCALAPPDATA']) / 'Cruces'
    resources = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
    executable = install(resources / 'payload', root)
    if not args.test_root:
        shortcut(executable)
    if not args.no_launch:
        subprocess.Popen([str(executable)], creationflags=subprocess.CREATE_NO_WINDOW)

if __name__ == '__main__':
    try:
        main()
    except Exception:
        if '--test-root' in sys.argv:
            raise
        ctypes.windll.user32.MessageBoxW(None, 'No se pudo instalar. Cierra Cruces y vuelve a ejecutar el instalador. Tus datos se conservan.', 'Cruces', 0x10)
        sys.exit(1)
