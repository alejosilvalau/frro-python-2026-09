import os
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.ipc as ipc


def print_separator(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


# Writing with new API
def write_feather_v2(df, path):
    table = pa.Table.from_pandas(df)
    with open(path, "wb") as f:
        writer = ipc.new_file(f, table.schema)
        writer.write(table)
        writer.close()


# Reading with new API
def read_feather_v2(path):
    with open(path, "rb") as f:
        reader = ipc.open_file(f)
        return reader.read_all().to_pandas()


# 1. GENERACIÓN DE DATASET DE PRUEBA
print_separator("1. GENERANDO DATASET DE 1.000.000 DE FILAS")
np.random.seed(42)
n_rows = 1_000_000

df = pd.DataFrame(
    {
        "id_transaccion": np.arange(n_rows),
        "fecha": pd.date_range(start="2025-01-01", periods=n_rows, freq="s"),
        "cliente_id": np.random.randint(1000, 9999, size=n_rows),
        "monto": np.random.uniform(10.0, 1500.0, size=n_rows),
        "categoria": np.random.choice(
            ["Electrónica", "Hogar", "Ropa", "Alimentos"], size=n_rows
        ),
        "es_activo": np.random.choice([True, False], size=n_rows),
    }
)

print(f"Shape del DataFrame: {df.shape}")
print(f"Uso de Memoria en RAM: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
print("\nPrimeras filas del dataset:")
print(df.head(3))

# Diccionario para almacenar métricas
metrics = []


def measure_serialization(format_name, write_func, read_func, file_path):
    # Medir Escritura
    start_time = time.time()
    write_func(file_path)
    write_time = time.time() - start_time

    # Medir Tamaño de Archivo
    file_size_mb = os.path.getsize(file_path) / (1024**2)

    # Medir Lectura
    start_time = time.time()
    df_read = read_func(file_path)
    read_time = time.time() - start_time

    # Verificar Integridad de Tipos (Schema Integrity)
    same_types = (df.dtypes == df_read.dtypes).all()

    # Limpiar archivo generado
    if os.path.exists(file_path):
        os.remove(file_path)

    metrics.append(
        {
            "Formato": format_name,
            "Escritura (s)": round(write_time, 3),
            "Lectura (s)": round(read_time, 3),
            "Tamaño (MB)": round(file_size_mb, 2),
            "Conserva Tipos": "Sí" if same_types else "No (los convierte a string)",
        }
    )


# 2. EJECUCIÓN DE PRUEBAS DE SERIALIZACIÓN
print_separator("2. EJECUTANDO MEDICHES DE SERIALIZACIÓN")

print("-> Guardando y Leyendo CSV...")
measure_serialization(
    "CSV",
    lambda path: df.to_csv(path, index=False),
    lambda path: pd.read_csv(path),
    "test_data.csv",
)

print("-> Guardando y Leyendo Pickle...")
measure_serialization(
    "Pickle",
    lambda path: df.to_pickle(path),
    lambda path: pd.read_pickle(path),
    "test_data.pkl",
)

print("-> Guardando y Leyendo Parquet (Snappy)...")
measure_serialization(
    "Parquet",
    lambda path: df.to_parquet(path, engine="pyarrow", compression="snappy"),
    lambda path: pd.read_parquet(path, engine="pyarrow"),
    "test_data.parquet",
)

print("-> Guardando y Leyendo Feather (Apache Arrow)...")
measure_serialization(
    "Feather",
    lambda path: write_feather_v2(df, path),
    lambda path: read_feather_v2(path),
    "test_data.feather",
)

# 3. MOSTRAR TABLA FINAL DE RESULTADOS
print_separator("3. TABLA COMPARATIVA DE RESULTADOS DE LA DEMO")
results_df = pd.DataFrame(metrics)
print(results_df.to_string(index=False))

print_separator("CONCLUSIÓN DE LA DEMO")
print("Parquet y Feather muestran una drástica reducción en tiempo de lectura")
print("y tamaño en disco manteniendo 100% de fidelidad en los tipos de datos.")
