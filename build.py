import os
import sys
import subprocess

def build_simple():
    """Упрощенная сборка без spec файла"""
    
    print("Упрощенная сборка...")
    
    # Команда для PyInstaller
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "main.py",
        "--onefile",
        "--console",  # Оставляем консоль для отладки
        "--name=WarehouseDashboard",
        "--clean",
        "--hidden-import=pandas._libs.tslibs.timedeltas",
        "--hidden-import=pandas._libs.tslibs.nattype", 
        "--hidden-import=pandas._libs.tslibs.timestamps",
        "--hidden-import=streamlit.web.cli",
        "--hidden-import=streamlit.runtime.scriptrunner",
        "--hidden-import=plotly.graph_objs",
        "--hidden-import=plotly.express",
        "--hidden-import=openpyxl",
        "--collect-all=streamlit",
        "--collect-all=plotly"
    ]
    
    try:
        print("Запуск PyInstaller...")
        subprocess.run(cmd, check=True)
        print("✓ Сборка завершена успешно!")
        
        # Создаем bat файл
        create_bat_file()
        
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при сборке: {e}")
        input("Нажмите Enter для выхода...")

def create_bat_file():
    """Создает bat файл для запуска"""
    bat_content = '''@echo off
chcp 65001 >nul
echo ========================================
echo    Warehouse Dashboard
echo ========================================
echo.
echo Запуск приложения...
dist\\WarehouseDashboard.exe
pause
'''
    
    with open('run_dashboard.bat', 'w', encoding='utf-8') as f:
        f.write(bat_content)
    print("✓ Bat файл создан: run_dashboard.bat")

if __name__ == '__main__':
    build_simple()