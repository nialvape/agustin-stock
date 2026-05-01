# Stock Management System

Sistema de gestión de stock para tiendas de accesorios de celulares.

## Estructura de Archivos

```
agustin-stock/
├── src/
│   ├── __init__.py
│   ├── google_sheets.py      # Autenticación y helpers de Google Sheets
│   └── sheet_config.py   # Configuración de sheets y tabs
├── .env                 # Variables de entorno (IDs de spreadsheets)
├── credentials.json    # Credenciales de Google Service Account
├── generate_order.py   # Script principal
└── README.md
```

## Configuración

### 1. Google Sheets

Cada variable en `.env` corresponde a un spreadsheet ID de Google Sheets:

```env
GLASS_TABLE=spreadsheet_id
ACCESORIOS_TABLE=spreadsheet_id
WANTED_GLASS_TABLE=spreadsheet_id
WANTED_ACCESORIOS_TABLE=spreadsheet_id
ORDER_GLASS_TABLE=spreadsheet_id
ORDER_ACCESORIOS_TABLE=spreadsheet_id
CONFIG_TABLE=spreadsheet_id
GOOGLE_APPLICATION_CREDENTIALS=./credentials.json
```

### 2. Service Account

1. Crear proyecto en [Google Cloud Console](https://console.cloud.google.com)
2. Habilitar **Google Sheets API**
3. Crear **Service Account** en IAM & Admin
4. Descargar JSON de credenciales
5. Compartir cada spreadsheet con el email del service account

### 3. Estructura de Sheets

| Spreadsheet | Tabs |
|------------|------|
| `GLASS_TABLE` | PANTALLA, CAMARAS, RELOJES-AIRPODS |
| `ACCESORIOS_TABLE` | ACCESORIOS |
| `WANTED_GLASS_TABLE` | STOCK |
| `WANTED_ACCESORIOS_TABLE` | STOCK |
| `ORDER_GLASS_TABLE` | COTO, MONTE, BELLA, PILAR, VELEZ, MERLO, SANFER, LA PLATA, GLEW, SAN MARTIN, ZARATE |
| `ORDER_ACCESORIOS_TABLE` | ACCE |
| `CONFIG_TABLE` | providers, product_mapping |

### Sheet: `providers`
| provider | code |
|----------|------|
| ProviderA | PDA001 |

### Sheet: `product_mapping`
Asocia cada producto con su proveedor y el nombre que usa el proveedor.

| product_name | store | stock_type | provider | provider_product_name |
|-------------|-------|-----------|----------|----------------------|
| Cable iPhone 1m | LA_PLATA | ACCESORIOS | ProviderA | CBL-IPH-1M-BK |

## Uso

```bash
# Generar órdenes para accesorios
python3 generate_order.py --store LA_PLATA --stock_type ACCESORIOS

# Generar órdenes para cristales
python3 generate_order.py --store LA_PLATA --stock_type GLASS
```

## Flujo de Ejecución

1. Lee el stock actual de `GLASS_TABLE` o `ACCESORIOS_TABLE`
2. Lee `CONFIG_TABLE` → `product_mapping` para mapeo de proveedores
3. Lee WANTED table → `desired_qty` para cada producto
4. Calcula `missing = desired - actual` para cada producto
5. **Actualiza** WANTED table con las diferencias
6. **Actualiza** ORDER tables:
   - `ORDER_ACCESORIOS_TABLE`: Busca producto en columna A, actualiza columna de la tienda
   - `ORDER_GLASS_TABLE`: Busca tab de la tienda, actualiza fila del producto

## Formato de datos

### WANTED Table (STOCK tab)
| product_name | actual_qty | desired_qty | missing_qty |
|--------------|------------|-------------|-------------|
| Cable iPhone 1m | 10 | 50 | 40 |

### ORDER_ACCESORIOS Table (ACCE tab)
- Columna A: productos (agrupados por tipo)
- Columnas B+: una por cada tienda (COTO, MONTE, BELLA, PILAR, etc.)

### ORDER_GLASS Table
- Una solapa por cada tienda
- Columna A: modelo, Columna B: cantidad

## Formato de Stock

### ACCESORIOS
- Formato: 2 columnas (producto, cantidad)
- Algunos productos están en columna C (con cantidad en columna B)

### GLASS
- Formato: matriz con marcas como headers (SAMSUNG, MOTOROLA, etc.)
- Columnas: COMUN, 5D, OSC
- Cada celda representa cantidad para ese modelo+marca+variante