# Reports - Archivos de entrada

Coloca aquí el archivo Excel de entrada con los registros que necesitan actualización de boletas.

## Formato esperado

El Excel debe tener al menos una columna `HESCode` que se usará para hacer el match con la respuesta de la API.

## Ejemplo

```
HESCode | ... otras columnas ...
176099  | ...
174122  | ...
```

El script agregará dos columnas nuevas:
- `BOLETA`: Código BTE si exitoso, 0 si error
- `DETALLE_ERRORES`: Mensaje de error o status
