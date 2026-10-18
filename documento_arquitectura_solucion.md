# Documento de Arquitectura de Solución - Piloto de Facturas Médicas

## 1. Visión General del Proyecto

Este proyecto implementa una arquitectura *serverless* e impulsada por eventos en **Microsoft Azure**, diseñada para automatizar la ingesta, validación, control de duplicados y segmentación del tráfico de **facturas médicas en formato PDF** provenientes de las IPS.

El objetivo principal es implementar un modelo experimental (A/B Testing o Grupo Control/Tratamiento) donde el **80%** de las facturas se derivan al proceso actual (manual/Excel) y el **20%** ingresa a un flujo automatizado de extracción con IA, garantizando además el aislamiento inmediato de archivos duplicados.

---

## 2. Diagrama de Arquitectura de Solución

<img width="521" height="472" alt="image" src="https://github.com/user-attachments/assets/5645216c-382e-4ca0-8389-188f5b74418d" />

---

## 3. Flujo de Datos y Orquestación (Extremo a Extremo)

El pipeline opera bajo un flujo de tres etapas claramente delimitadas:

1. **Ingesta y Almacenamiento Inicial (Paso 1):**
   * La IPS deposita el documento PDF en el contenedor/directorio origen (`IPS`).
   * El archivo es movido o registrado inmediatamente en la carpeta `Crudo` dentro de **Azure Blob Storage** como punto de partida sin procesar.

2. **Detección e Invocación (Paso 2):**
   * **Azure Logic Apps** detecta el evento de creación del nuevo PDF en el almacenamiento (`Trigger`).
   * Desencadena de forma inmediata la ejecución de la **Azure Function** encargada de la lógica principal.

3. **Procesamiento, Control de Duplicados y Ruteo (Paso 3):**
   * La **Azure Function** lee el PDF desde `Crudo`, calcula su firma de integridad (hash SHA-256) y valida contra el registro histórico si se trata de una factura duplicada.
   * **Si es duplicado:** Mueve automáticamente la factura a la carpeta `Duplicados`.
   * **Si es única:** Aplica el algoritmo de segmentación aleatoria estratificada:
     * **80% del tráfico:** Se mueve a la carpeta `Flujo_actual` (para procesamiento tradicional).
     * **20% del tráfico:** Se mueve a la carpeta `Flujo_nuevo` (para el flujo de IA con Document Intelligence / ML).

---

## 4. Desglose Técnico de la Infraestructura

### A. Capas de Almacenamiento (`Azure Blob Storage`)
* **`IPS` / `Crudo`:** Directorios de ingesta en la zona de aterrizaje (*landing zone*) para conservar la copia íntegra del archivo original.
* **`Flujo_actual`:** Almacena los PDFs asignados al grupo de control (procesamiento manual/actual).
* **`Flujo_nuevo`:** Almacena los PDFs asignados al grupo de tratamiento (procesamiento automatizado con IA).
* **`Duplicados`:** Aísla las facturas repetidas para evitar reprocesamientos y mantener la calidad de los datos.

### B. Cómputo y Orquestación
* **`Azure Logic Apps` (`Trigger`):** Conector desacoplado basado en eventos que escucha el almacenamiento y gestiona la activación del proceso sin requerir infraestructura siempre encendida.
* **`Azure Function` (`Validación y Ruteo`):** Microservicio *serverless* escrito en código nativo (Python/C#) que contiene las reglas de negocio para:
  1. Cálculo de hash y comparación de metadatos.
  2. Lógica de sorteo (80/20) según estratificación (IPS, cuantía o complejidad).
  3. Mapeo y traslado físico del archivo hacia la carpeta de destino correspondiente en Blob Storage.

---

## 5. Criterios de Seguridad y Gobierno

* **Inmutabilidad:** Los documentos en `Crudo` sirven como evidencia primaria de auditoría.
* **Aislamiento de Errores:** La carpeta `Duplicados` evita contaminar las métricas del piloto y previene sobrecostos de extracción por IA en archivos repetidos.
* **Acceso por Roles (RBAC):** Acceso restringido por identidades administradas (*Managed Identities*) entre Logic Apps, Azure Functions y las carpetas de Blob Storage.
