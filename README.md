# Stock Management System

Sistema de gestión de stock para tiendas de accesorios de celulares.

## Estructura de Archivos

```
agustin-stock/
├── config/
│   └── config.xlsx          # Configuración central
├── tables/
│   ├── ACCESORIOS_LA_PLATA_13-04.xlsx  # Stock actual (fuente)
│   ├── GLASS_LA_PLATA_13-04.xlsx        # Stock actual (fuente)
│   ├── WANTED_ACCESORIOS_LA_PLATA.xlsx  # Diferencia calculada
│   ├── WANTED_GLASS_LA_PLATA.xlsx
│   └── ORDER_ACCESORIOS_LA_PLATA_{PROVIDER}.xlsx  # Órdenes por proveedor
└── generate_order.py        # Script principal
```

## Configuración (`config/config.xlsx`)

### Sheet: `providers`
Lista de proveedores.

| provider | code |
|----------|------|
| ProviderA | PDA001 |

### Sheet: `product_mapping`
Asocia cada producto con su proveedor y el nombre que usa el proveedor.

| product_name | store | stock_type | provider | provider_product_name |
|-------------|-------|-----------|----------|----------------------|
| Cable iPhone 1m | LA_PLATA | ACCESORIOS | ProviderA | CBL-IPH-1M-BK |

### Sheet: `desired_stock`
Cantidades deseadas por producto (se edita manualmente).

| store | stock_type | product_name | desired_qty |
|-------|-----------|--------------|-------------|

## Uso

```bash
# Generar órdenes para accesorios
python3 generate_order.py --store LA_PLATA --stock_type ACCESORIOS

# Generar órdenes para cristales
python3 generate_order.py --store LA_PLATA --stock_type GLASS
```

## Flujo de Ejecución

1. Lee el archivo de stock actual (`ACCESORIOS_LA_PLATA_*.xlsx`)
2. Lee `config.xlsx` → `desired_stock` para obtener cantidades deseadas
3. Calcula `missing = desired - actual` para cada producto
4. **Actualiza** `WANTED_ACCESORIOS_LA_PLATA.xlsx` con las diferencias
5. **Genera** archivos `ORDER_*_{PROVIDER}.xlsx` por cada proveedor que tenga productos faltantes

## Formato de Salida

### WANTED File
| product_name | actual_qty | desired_qty | missing_qty |
|--------------|------------|-------------|-------------|

### ORDER File (por proveedor)
| provider_product_name | quantity |
|-----------------------|----------|

## Notas sobre Archivos de Stock

### ACCESORIOS
- Formato: 2 columnas (producto, cantidad)
- Algunos productos están en columna C (con cantidad en columna B)

### GLASS
- Formato: matriz con marcas como headers (SAMSUNG, MOTOROLA, etc.)
- Columnas: COMUN, 5D, OSC
- Cada celda representa cantidad para ese modelo+marca+variante

---

## Roadmap: Excel Online

### Situación Actual
Los archivos Excel están en el sistema de archivos local.

### Visión Futura
Migrar a Excel online (SharePoint/OneDrive) para acceso multi-usuario.

### Opciones Técnicas

#### Opción 1: Microsoft Graph API + SharePoint
- Acceso via API de Microsoft 365
- Requiere autenticación OAuth
- Ideal para integración directa con Microsoft Excel Online

```python
# Conceptual - no implementado
from office365.runtime.auth.authentication_context import AuthenticationContext
from office365.sharepoint.client_context import ClientContext

ctx = ClientContext("https://tenant.sharepoint.com/sites/store")
ctx.acquire_token_for_app(client_id, client_secret)
```

#### Opción 2: Google Sheets API
- Si se migra a Google Sheets
- Más simple de implementar
- Requiere credenciales Google Cloud

#### Opción 3: pandas + remote file access
- Acceso a archivos en OneDrive/Google Drive como archivos remotos
- Menor complejidad inicial
- Ejemplo: `pd.read_excel("https://onedrive.live.com/download?...")`

### Pasos para Implementación

1. **Autenticación**
   - Registrar app en Azure AD (para Microsoft) o Google Cloud (para Google)
   - Configurar permisos de lectura/escritura

2. **Abstracción de Acceso**
   - Crear capa `StockProvider` abstracta
   - Implementar `LocalStockProvider` y `OnlineStockProvider`

```python
class StockProvider(ABC):
    @abstractmethod
    def load_stock(self, store: str, stock_type: str) -> dict:
        pass

class LocalStockProvider(StockProvider):
    def load_stock(self, store, stock_type):
        # implementación actual
        pass

class OnlineStockProvider(StockProvider):
    def load_stock(self, store, stock_type):
        # implementación futura
        pass
```

3. **Conflictos de Escritura**
   - El archivo WANTED se actualiza frecuentemente
   - Considerar locking o sistema de turnos
   - Posible solución: cola de cambios en lugar de escritura directa

4. **Configuración**
   - Agregar sheet `settings` en config.xlsx:
   ```python
   {
       "storage": "local",  # o "onedrive", "googlesheets"
       "onedrive_url": "https://tenant.sharepoint.com/sites/stock/...",
   }
   ```

### Consideraciones de Seguridad

- No guardar credenciales en código
- Usar environment variables o Azure Key Vault
- Implementar rotation de tokens

### Métricas de Monitoreo (para versión online)

- Latencia de lectura/escritura
- Conflictos de edición detectados
- Tiempo de sync entre usuarios
