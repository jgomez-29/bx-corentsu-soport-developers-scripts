/**
 * Script simplificado para copiar y pegar directamente en mongo shell
 * 
 * OPTIMIZADO PARA MILLONES DE REGISTROS:
 *   - Verifica y crea índice en 'orderId' automáticamente
 *   - Usa hint() para forzar uso del índice
 *   - Optimizado para colecciones grandes
 * 
 * INSTRUCCIONES:
 *   1. Edita las constantes de configuración abajo
 *   2. Copia TODO este código
 *   3. Pégalo en mongo shell y presiona Enter
 * 
 * NOTA IMPORTANTE:
 *   Para mejor rendimiento, el patrón debería comenzar con texto fijo.
 *   Ejemplo: "TEST-ORDER-CONTAINER" es mejor que "^.*TEST.*"
 *   Esto permite a MongoDB usar el índice de manera más eficiente.
 * 
 * CONFIGURACIÓN - Edita estos valores:
 */

// ============================================================================
// ⚙️ CONFIGURACIÓN - EDITA AQUÍ
// ============================================================================

const DRY_RUN = true;  // true = simulación (seguro), false = elimina realmente
const COLLECTION_NAME = "orders";  // Nombre de tu colección
const ORDER_ID_PATTERN = "TEST-ORDER-CONTAINER";  // Patrón a buscar
const CASE_INSENSITIVE = true;  // true = no distingue mayúsculas/minúsculas

// ============================================================================
// 🚀 EJECUCIÓN - No edites nada de aquí en adelante
// ============================================================================

(function() {
    print("=".repeat(70));
    print("🧹 LIMPIEZA DE ÓRDENES DE PRUEBA");
    print("=".repeat(70));
    print();
    
    print("📊 Configuración:");
    print(`   Base de datos: ${db.getName()}`);
    print(`   Colección: ${COLLECTION_NAME}`);
    print(`   Patrón: "${ORDER_ID_PATTERN}"`);
    print(`   Case-insensitive: ${CASE_INSENSITIVE ? "Sí" : "No"}`);
    print(`   Modo: ${DRY_RUN ? "DRY-RUN (simulación)" : "ELIMINACIÓN REAL"}`);
    print();
    
    // Verificar que la colección existe
    const collections = db.getCollectionNames();
    if (!collections.includes(COLLECTION_NAME)) {
        print(`❌ Error: La colección '${COLLECTION_NAME}' no existe`);
        return;
    }
    
    // Verificar/crear índice en orderId para optimizar la búsqueda
    print("🔍 Verificando índice en orderId...");
    const indexes = db[COLLECTION_NAME].getIndexes();
    const hasOrderIdIndex = indexes.some(idx => idx.key && idx.key.orderId !== undefined);
    
    if (!hasOrderIdIndex) {
        print("⚠️  No se encontró índice en 'orderId'. Creando índice para optimizar...");
        try {
            db[COLLECTION_NAME].createIndex({ orderId: 1 });
            print("✅ Índice creado exitosamente");
        } catch (e) {
            print(`⚠️  Advertencia: No se pudo crear el índice: ${e.message}`);
            print("   La operación continuará pero puede ser más lenta");
        }
        print();
    } else {
        print("✅ Índice en 'orderId' encontrado");
        print();
    }
    
    // Construir query con regex
    // IMPORTANTE: Usar patrón que comience con el texto para aprovechar el índice
    // Si el patrón no comienza con texto fijo, MongoDB no puede usar el índice eficientemente
    const regexOptions = CASE_INSENSITIVE ? "i" : "";
    const query = { orderId: new RegExp(ORDER_ID_PATTERN, regexOptions) };
    
    // Contar registros (usando hint para forzar uso del índice si existe)
    print("🔍 Buscando registros...");
    let count;
    try {
        count = db[COLLECTION_NAME].countDocuments(query, { hint: { orderId: 1 } });
    } catch (e) {
        // Si hint falla, usar sin hint
        count = db[COLLECTION_NAME].countDocuments(query);
    }
    print(`   Registros encontrados: ${count}`);
    print();
    
    if (count === 0) {
        print("✅ No hay registros para eliminar");
        return;
    }
    
    // Mostrar algunos ejemplos (limitado para no afectar performance)
    if (count > 0 && count <= 10000) {
        print("📋 Ejemplos de orderIds que se eliminarían:");
        try {
            const sample = db[COLLECTION_NAME].find(query, { orderId: 1, _id: 0 })
                .hint({ orderId: 1 })
                .limit(5);
            let examples = [];
            while (sample.hasNext()) {
                const doc = sample.next();
                if (doc.orderId) {
                    examples.push(doc.orderId);
                }
            }
            print(`   ${examples.join(", ")}${count > 5 ? ` ... (+${count - 5} más)` : ""}`);
        } catch (e) {
            // Si hint falla, continuar sin ejemplos
            print("   (No se pudieron obtener ejemplos)");
        }
        print();
    } else if (count > 10000) {
        print("📋 Nota: Se encontraron muchos registros. Omitiendo ejemplos para optimizar.");
        print();
    }
    
    if (DRY_RUN) {
        print("=".repeat(70));
        print("🔍 MODO DRY-RUN (SIMULACIÓN)");
        print("=".repeat(70));
        print("✅ Esta es una simulación. NO se eliminarán registros.");
        print(`✅ Se eliminarían ${count} registros si ejecutaras con DRY_RUN = false`);
        print("=".repeat(70));
    } else {
        print("=".repeat(70));
        print("⚠️  ⚠️  ⚠️  MODO DE ELIMINACIÓN REAL ⚠️  ⚠️  ⚠️");
        print("=".repeat(70));
        print("❌ ADVERTENCIA: Se ELIMINARÁN registros de la base de datos.");
        print("❌ Esta operación NO se puede deshacer.");
        print();
        print("💡 Si no estás seguro, presiona Ctrl+C ahora para cancelar.");
        print();
        print("   Esperando 5 segundos antes de continuar...");
        print("=".repeat(70));
        
        sleep(5000);
        print();
        print("▶️  Eliminando registros...");
        print();
        
        const startTime = new Date();
        
        // Usar hint para forzar uso del índice y optimizar la eliminación
        let result;
        try {
            // Intentar con hint para usar el índice
            result = db[COLLECTION_NAME].deleteMany(query, { hint: { orderId: 1 } });
        } catch (e) {
            // Si hint falla, usar sin hint (puede ser más lento)
            print("⚠️  Advertencia: No se pudo usar hint, ejecutando sin optimización de índice");
            result = db[COLLECTION_NAME].deleteMany(query);
        }
        
        const endTime = new Date();
        const duration = ((endTime - startTime) / 1000).toFixed(2);
        
        print();
        print("=".repeat(70));
        print("📊 RESUMEN");
        print("=".repeat(70));
        print(`   Registros eliminados: ${result.deletedCount}`);
        print(`   Tiempo transcurrido: ${duration}s`);
        print();
        
        // Verificar que se eliminaron todos (usando hint si es posible)
        let afterCount;
        try {
            afterCount = db[COLLECTION_NAME].countDocuments(query, { hint: { orderId: 1 } });
        } catch (e) {
            afterCount = db[COLLECTION_NAME].countDocuments(query);
        }
        
        if (afterCount > 0) {
            print(`⚠️  Advertencia: Aún quedan ${afterCount} registros`);
            print(`   Esto puede ser normal si algunos registros no coincidían exactamente con el patrón.`);
        } else {
            print("✅ Todos los registros fueron eliminados exitosamente");
        }
        print("=".repeat(70));
    }
})();
