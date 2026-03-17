/** @odoo-module */
import { _t } from "@web/core/l10n/translation";
import { NotaCreditoPopUp } from "@pos_fiscal_printer/app/popup/nota_credito_popup";

const encoder = new TextEncoder();
const CHAR_MAP = {
    "ñ": "n", "Ñ": "N", "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
    "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "ä": "a", "ë": "e",
    "ï": "i", "ö": "o", "ü": "u", "Ä": "A", "Ë": "E", "Ï": "I", "Ö": "O", "Ü": "U",
};
const EXPRESSION = new RegExp(`[${Object.keys(CHAR_MAP).join("")}]`, "g");

// Pachacutec: v67 - cleanText RADICAL (NFD + UpperCase) - Preservando espacios
export function cleanText(string) {
    if (!string) return "";
    try {
        let clean = string.normalize("NFD");
        clean = clean.replace(/[\u0300-\u036f]/g, "");
        clean = clean.replace(/ñ/g, "n").replace(/Ñ/g, "N");
        clean = clean.toUpperCase();
        clean = clean.replace(/[^\x20-\x7E]/g, "");
        // Pachacutec: v67 - Eliminar .trim() para que el padding de 40 sea exacto
        return clean.replace(/[!|*]/g, " ");
    } catch (e) {
        console.error("Error en cleanText v67:", e);
        return String(string).toUpperCase().replace(/[^\x20-\x7E]/g, "");
    }
}

// Pachacutec: v108 - Función Sanitize v16 Truth (High Fidelity)
// Usa el CHAR_MAP explícito para garantizar ASCII puro y evitar UTF-8 (2 bytes).
export function sanitize(string) {
    if (!string) return "";
    return string.replace(EXPRESSION, (char) => CHAR_MAP[char])
        .replace(/[!|*]/g, " ")
        .replace(/[^\x20-\x7E]/g, "");
}

// Pachacutec: v106 - Función Convert v16 Truth
export function convert(amount, fixed = 2) {
    return (amount || 0).toFixed(fixed).replace(".", ",");
}

// Pachacutec: v66 - Restauración Estricta XOR v16 (1 solo byte de Checksum)
// Pachacutec: v73 - Restauración XOR Binario (1 solo byte)
// Requisito final HKA: 1 solo byte binario para el checksum.
// Pachacutec: v97 - Reversión Final v16 Pure (XOR EXCLUYENTE STX)
// Validado Matemáticamente: v16 Pure SIEMPRE excluye el STX (2) del Checksum.
// El LRC es DATA ^ ETX solamente.
export function toBytes(command) {
    const encoder = new TextEncoder();
    const dataBytes = Array.from(encoder.encode(command));
    const ETX = 3;
    const STX = 2;

    // v97: DATA + ETX solamente (v16 Pure). Independiente del tipo de comando.
    let lrc = 0; 
    for (const byte of dataBytes) {
        lrc ^= byte;
    }
    lrc ^= ETX;

    // La trama física SI incluye STX al inicio: [STX, DATA, ETX, LRC]
    const finalFrame = [STX, ...dataBytes, ETX, lrc];
    return new Uint8Array(finalFrame);
}

// FiscalPrinterMixin as a plain object with methods only.
// Getters for 'port' and 'readerStream' must be defined on the component ensuring this mixin.
export const FiscalPrinterMixin = {
    async setPort() {
        try {
            if (!this.port) {
                const ports = await navigator.serial.getPorts();
                console.log("Puertos ya autorizados:", ports.length);
                let port;

                // Detailed info for debugging
                for (const p of ports) {
                    const info = p.getInfo();
                    console.log("Info puerto:", info);
                }

                // If there's only one authorized port, we might try it, but safer to request if it fails
                if (ports.length === 1) {
                    port = ports[0];
                    console.log("Intentando reutilizar puerto único autorizado...");
                } else {
                    console.log("Solicitando selección de puerto al usuario...");
                    port = await navigator.serial.requestPort();
                }

                // Pachacutec: v84 - FORZAR VELOCIDAD (HKA80 Self-Test)
                // Se ignoran variables externas y se fuerzan 19200 baudios y paridad even.
                const parity = "even";
                const baudRate = 19200;
                console.warn("[FISCAL] v84 - Forzando Puerto: 19200 baudios, Parity: Even");

                try {
                    await port.open({
                        baudRate: baudRate,
                        parity: parity,
                        dataBits: 8,
                        stopBits: 1,
                    });
                    console.log("Puerto abierto exitosamente a 19200.");
                } catch (e) {
                    if (e.name === "InvalidStateError") {
                        console.log("El puerto ya estaba abierto. Continuando...");
                    } else if (ports.length >= 1 && (e.name === "NetworkError" || e.name === "SecurityError")) {
                        console.warn("Fallo al reutilizar puerto persistente (" + e.name + "), solicitando nuevo...");
                        port = await navigator.serial.requestPort();
                        await port.open({
                            baudRate: baudRate,
                            parity: parity,
                            dataBits: 8,
                            stopBits: 1,
                        });
                    } else {
                        throw e;
                    }
                }
                this.port = port;
            }
            return true;
        } catch (error) {
            console.error("Error crítico en setPort:", error);
            let msg = _t("Error al abrir el puerto serial.");
            if (error.name === "NetworkError") {
                msg = _t("El puerto está siendo usado por otra aplicación o no tiene permisos.");
            }
            this.env.services.notification.add(msg + " (" + error.name + ")", { type: "danger" });
            this.port = false;
            return false;
        }
    },

    async escribe_leer(command, is_linea, is_retry = false) {
        if (!this.port) return false;
        var comando_cod = toBytes(command);
        console.log("Escribiendo comando: ");
        console.log(command)
        console.log("Comando codificado: ");
        console.log(comando_cod);

        this.writer = this.port.writable.getWriter();
        var signals_to_send = { dataTerminalReady: true };
        if (this.pos.config.connection_type === "usb_serial") {
            signals_to_send = { requestToSend: true };
        }
        try {
            await this.port.setSignals(signals_to_send);
        } catch (e) {
            console.warn("Error al setear señales (normal en emuladores):", e);
        }

        var signals = { clearToSend: true, dataSetReady: true };
        try {
            signals = await this.port.getSignals();
            console.log("signals: ", signals);
        } catch (e) {
            console.warn("Error al leer señales (normal en emuladores):", e);
        }

        if (this.pos.config.connection_type === "usb_serial") {
            console.log("signals DSR: ", signals.dataSetReady);
            console.log("signals CTS: ", signals.clearToSend);
        } else {
            console.log("signals CTS: ", signals.clearToSend);
            console.log("signals DSR: ", signals.dataSetReady);
        }
        if (signals.clearToSend || signals.dataSetReady) {
            await new Promise(
                (res) => setTimeout(() => res(this.writer.write(comando_cod)), 20)
            );
            await this.writer.releaseLock();
            this.writer = false;
            if (this.read_Z) {
                console.log("Esperando 12 seundos para leer Z o X....");
                await new Promise(
                    (res) => setTimeout(() => res(), 12000)
                );
            }
            console.log("Empezando lectura");
            while (!this.port.readable) {
                console.log("Esperando puerto");
                if (this.reader) {
                    await this.reader.releaseLock();
                    this.reader = false;
                }
                await new Promise(
                    (res) => setTimeout(() => res(), 50)
                );
            }

            await new Promise(
                (res) => setTimeout(() => res(), 10)
            );
            if (this.reader) {
                await this.reader.releaseLock();
                this.reader = false;
            }
            if (this.port.readable) {
                this.reader = this.port.readable.getReader();
                var leer = true;
            } else {
                var leer = false;
            }

            var esperando = 0;
            var responseData = [];
            while (leer) {
                try {
                    const { value, done } = await this.reader.read();
                    if (value && value.byteLength >= 1) {
                        console.log("Respuesta de comando: ", value, " Byte 0: ", value[0]);
                        
                        // Si es un comando de status (S1, S2, S3), la impresora responde con STX (2) + DATA + ETX (3) + LRC
                        if (command.length === 2 && command.startsWith("S") && value[0] === 2) {
                            responseData = Array.from(value);
                            console.log("[FISCAL] v74 - Respuesta Status detectada:", responseData);
                            leer = false;
                            await this.reader.releaseLock();
                            this.reader = false;
                            return responseData; // Devolvemos la trama completa
                        }

                        if (value[0] == 6) {
                            console.log("Comando aceptado (ACK)");
                            leer = false;
                            await this.reader.releaseLock();
                            this.reader = false;
                            return true;
                        } else if (value[0] == 21) {
                            console.error("[FISCAL] Impresora devolvió NAK.");
                            leer = false;
                            await this.reader.releaseLock();
                            this.reader = false;

                            // Pachacutec: v103 - Diagnóstico en Caliente
                            await this.fetchStatusDiagnosis();

                            return false; 
                        }
                    } else {
                        console.log("No hay datos...");
                        esperando++;
                        await new Promise(res => setTimeout(res, 200));
                    }
                    if (esperando > 20) {
                        console.error("[FISCAL] Timeout esperando respuesta");
                        this.printing = false;
                        leer = false;
                        break;
                    }
                } catch (error) {
                    console.error("Error al leer puerto:", error);
                    leer = false;
                } finally {
                    if (this.reader) {
                        try { await this.reader.releaseLock(); } catch (e) { }
                        this.reader = false;
                    }
                }
            }
            return false;
        } else {
            console.log("Error signals CTS: ", signals);
            this.printing = false;
            return false;
        }
    },

    async write() {
        this.modal_imprimiendo = Swal.fire({
            title: 'Imprimiendo',
            text: 'Por favor espere.',
            imageUrl: '/pos_fiscal_printer/static/src/image/impresora.gif',
            imageWidth: 100,
            imageHeight: 100,
            imageAlt: 'Imprimiendo',
            allowOutsideClick: false,
            allowEscapeKey: false,
            allowEnterKey: false,
            showConfirmButton: false,
        });

        // ELIMINADO: v86 - Limpieza inicial (Comando 7)
        // Se elimina en v87 porque causaba NAK innecesario en algunos equipos.
        
        const TIME = this.pos.config.x_fiscal_commands_time || 750;
        this.printing = true;
        // Pachacutec: v52 - ELIMINADA sanitización global que borraba '!', '*', '|'
        console.log("Comandos a enviar: ", this.printerCommands);
        var cantidad_comandos = this.printerCommands.length;
        for (let i = 0; i < this.printerCommands.length; i++) {
            const command = this.printerCommands[i];
            var is_linea = false;
            if (command.substring(0, 1) === ' ' || command.substring(0, 1) === '!' || command.substring(0, 1) === 'd' || command.substring(0, 1) === '-') {
                is_linea = true;
            }
            if (this.printing) {
                const success = await new Promise((res) => {
                    setTimeout(async () => {
                        console.warn(`[FISCAL] Enviando (${i + 1}/${this.printerCommands.length}):`, command);
                        const res_ok = await this.escribe_leer(command, is_linea);
                        res(res_ok);
                    }, TIME);
                });

                if (success) {
                    console.warn(`[FISCAL] Comando [${i + 1}] EXITOSO (ACK).`);
                } else {
                    // Pachacutec: v70 - Tolerancia a NAK en encabezados opcionales (i00-i03)
                    if (command.substring(0, 2) === "i0") {
                        console.warn("[FISCAL] v70 - Encabezado opcional falló (NAK), continuando factura...", command);
                        continue;
                    }

                    console.error("[FISCAL] Error en comando MANDATORIO:", command, ". Abortando impresión.");
                    this.printing = false;
                    break; 
                }

                // Pachacutec: v74 - Sincronización vía Status S2
                // Si el comando enviado fue "S2", el 'success' contiene la trama de respuesta.
                if (command === "S2" && Array.isArray(success)) {
                    console.log("[FISCAL] v74 - Analizando Status S2 para sincronizar montos...");
                    // El Manual v8.5.0 indica que S2 devuelve montos acumulados.
                    // Aquí podríamos inyectar lógica para ajustar el siguiente comando de pago si hay discrepancia.
                }

                cantidad_comandos--;
            }
        }
        this.modal_imprimiendo.close();
        if (cantidad_comandos == 0) {
            console.log("Comandos finalizados");
            if (this.order) {
                this.order.impresa = true;
                Swal.fire({
                    position: 'top-end',
                    icon: 'success',
                    title: 'Impresión finalizada con éxito',
                    showConfirmButton: false,
                    timer: 1500
                });
            }

        } else {
            //error en impresion
            console.log("Error en impresion, factura anulada");
            Swal.fire({
                position: 'top-end',
                icon: 'error',
                title: 'Error en impresion, factura anulada',
                showConfirmButton: false,
                timer: 2500
            });
        }

        window.clearTimeout(this.timeout);
        this.printerCommands = [];
        this.printing = false;

        this.writer = false;
        if (this.read_s2 && cantidad_comandos == 0) {
            //mandar comando S2 y leer
            await this.write_s2();

        }
        if (this.read_Z) {
            //mandar comando Z y leer
            const { confirmed } = await this.showPopup("ReporteZPopUp", { cancelKey: "Q", confirmKey: "Y" });
            if (confirmed) {
                await this.write_Z();
            }

        }
        console.log("Factura finalizada, puerto permanece abierto.");
    },

    async write_s2() {
        this.writer = this.port.writable.getWriter();
        const TIME = this.pos.config.x_fiscal_commands_time || 750;
        this.printerCommands = ["S1"];
        this.printerCommands = this.printerCommands.map(toBytes);
        console.log("Escribiendo S1", this.printerCommands);
        for (const command of this.printerCommands) {
            await new Promise(
                (res) => setTimeout(() => res(this.writer.write(command)), TIME)
            );
        }
        window.clearTimeout(this.timeout);
        this.printerCommands = [];
        await this.writer.releaseLock();
        this.writer = false;
        var signals_to_send = { dataTerminalReady: true };
        if (this.pos.config.connection_type === "usb_serial") {
            signals_to_send = { requestToSend: true };
        }
        try {
            await this.port.setSignals(signals_to_send);
        } catch (e) {
            console.warn("Error al setear señales (normal en emuladores):", e);
        }

        console.log("Leyendo S1", this.port.readable)

        var signals = { clearToSend: true, dataSetReady: true };
        try {
            signals = await this.port.getSignals();
            console.log("signals: ", signals);
        } catch (e) {
            console.warn("Error al leer señales (normal en emuladores):", e);
        }

        if (this.pos.config.connection_type === "usb_serial") {
            console.log("signals DSR: ", signals.dataSetReady);
            console.log("signals CTS: ", signals.clearToSend);
        } else {
            console.log("signals CTS: ", signals.clearToSend);
            console.log("signals DSR: ", signals.dataSetReady);
        }
        if (signals.clearToSend || signals.dataSetReady) {
            if (this.reader) {
                this.reader.releaseLock();
                this.reader = false;
            }
            if (this.port.readable) {
                this.reader = this.port.readable.getReader();
            }
            var leer = true;
            var contador = 0;
            while (this.port.readable && leer) {
                try {
                    while (leer) {
                        const { value, done } = await this.reader.read();
                        var string = new TextDecoder().decode(value);
                        console.warn("[FISCAL] Respuesta S1 recibida:", string);
                        
                        if (string.length > 0) {
                            // Pachacutec: v36 - CAPTURA ROBUSTA CON REGEX (Compatible con cualquier impresora HKA)
                            // Buscamos una secuencia de dígitos (generalmente 8 o más) que represente el número fiscal
                            const match = string.match(/\d{5,15}/g); 
                            if (match && match.length > 0) {
                                // El número de factura suele ser el último o penúltimo grupo de números grandes
                                // En HKA-NG el reporte S1 devuelve varios campos, el correlativo es clave.
                                const num_factura = match[match.length - 1]; 
                                console.warn("[FISCAL] Numero de factura extraído con Regex: ", num_factura);
                                this.order.num_factura = num_factura.padStart(8, "0");
                                leer = false;
                                break;
                            } else {
                                contador++;
                                await new Promise(res => setTimeout(res, 200));
                                if (contador > 15) { leer = false; break; }
                            }
                        } else {
                            contador++;
                            await new Promise(res => setTimeout(res, 200));
                            if (contador > 15) { leer = false; break; }
                        }
                    }
                } catch (error) {
                    leer = false;
                    console.error("Error en lectura write_s2:", error);
                } finally {
                    leer = false;
                }
            }

            // Pachacutec: v37 - Persistencia garantizada del estado 'impresa'
            if (this.order.num_factura) {
                console.warn("[FISCAL] Marcando orden como impresa permanentemente.");
                this.order.impresa = true;
                
                await this.orm.call(
                    'pos.order',
                    'set_num_factura',
                    [this.order.id, this.order.name, this.order.num_factura]
                );
            } else {
                console.error("[FISCAL] Imposible marcar como impresa: número de factura no recibido.");
            }

        }

        this.printerCommands = [];
        this.read_s2 = false;
    },

    async write_Z() {
        this.read_Z = true;
        this.writer = this.port.writable.getWriter();
        const TIME = this.pos.config.x_fiscal_commands_time || 750;
        
        // Pachacutec: v36 - REPORTE Z DINÁMICO (Compatible con v16 pero sin fecha fija)
        // Usamos I0Z para cierre diario (Z Report) que es lo que el 99% de las veces se quiere
        this.printerCommands = ["I0Z"]; 
        const command = this.printerCommands[0];
        
        // Pachacutec: v37 - VALIDACIÓN DE REPORTE (Usando escribe_leer para detectar errores)
        if (this.writer) { await this.writer.releaseLock(); this.writer = false; }
        
        const success = await this.escribe_leer(command, false);
        if (!success) {
            console.error("[FISCAL] Error al solicitar Reporte Z.");
            this.read_Z = false;
            return;
        }

        window.clearTimeout(this.timeout);
        this.printerCommands = [];
        this.writer.releaseLock();
        this.writer = false;
        await new Promise(
            (res) => setTimeout(() => res(), 12000)
        );
        console.log("Leyendo U4z02002230200223", this.port.readable)
        this.reader = false;
        if (this.port.readable) {
            this.reader = this.port.readable.getReader();
        }

        while (this.port.readable && this.read_Z) {
            try {
                while (this.read_Z) {
                    const { value, done } = await this.reader.read();
                    if (done) {
                        console.log("Done");
                        this.read_Z = false;
                        this.reader.releaseLock();
                        this.reader = false;
                        this.read_Z = false;
                        break;
                    }
                    console.log(value);
                    var string = new TextDecoder().decode(value);
                    console.log(string);
                    console.log('Desglozando U4z02002230200223');
                    const myArray = string.split('\n');
                    console.log(myArray);
                    // Break loop after receiving data to prevent hanging
                    if (string.length > 0) {
                        this.read_Z = false;
                        break;
                    }
                }
            } catch (error) {
                console.error("Error en lectura write_Z:", error);
                this.read_Z = false;
            } finally {
                if (this.reader) {
                    try {
                        this.reader.releaseLock();
                    } catch (e) { }
                    this.reader = false;
                }
            }
        }

        this.printerCommands = [];
        this.read_Z = false;
    },

    async actionPrint() {
        if (this.pos.config.connection_type === "api") {
            return this.printViaApi();
        }

        if (this.printing_lock) {
            console.warn("[FISCAL] Bloqueo de concurrencia activo. Esperando...");
            return;
        }
        this.printing_lock = true;
        try {
            const result = await this.setPort();
            if (!result) return;
            await this.write();
        } finally {
            this.printing_lock = false;
        }
    },

    async printViaUSB() {
        console.log("Detectando dispositivos via USB");
        let devices = await navigator.usb.getDevices();
        devices.forEach(device => {
            alert(device);
            if (device.productName === "Fiscal Printer") {
                console.log("Impresora Fiscal encontrada");
                this.device = device;
            }
        });
        Swal.fire({
            icon: 'error',
            title: 'Error en impresion, conexión via USB no disponible',
            showConfirmButton: true,
        });
    },

    async printZViaApi() {
        console.log("Imprimiendo Reporte Z via API");
        this.modal_imprimiendo = Swal.fire({
            title: 'Imprimiendo',
            text: 'Por favor espere.',
            imageUrl: '/pos_fiscal_printer/static/src/image/impresora.gif',
            imageWidth: 100,
            imageHeight: 100,
            imageAlt: 'Imprimiendo',
            allowOutsideClick: false,
            allowEscapeKey: false,
            allowEnterKey: false,
            showConfirmButton: false,
            timer: 1500
        });
        var url = this.pos.config.api_url + "/zreport/print";
        try {
            const response = await fetch(url, {
                headers: {
                    'Bypass-Tunnel-Reminder': 'true'
                },
                credentials: 'include'
            });
            if (response.ok) {
                Swal.fire({
                    position: 'top-end',
                    icon: 'success',
                    title: 'Impresión finalizada con éxito',
                    showConfirmButton: false,
                    timer: 1500
                });
            } else {
                Swal.fire({
                    icon: 'error',
                    title: 'Error en impresión',
                    showConfirmButton: true,
                });
            }
        } catch (error) {
            console.error("Error en printZViaApi:", error);
            Swal.fire({
                icon: 'error',
                title: 'Error de conexión con la API',
                text: error.message,
                showConfirmButton: true,
            });
        } finally {
            if (this.modal_imprimiendo) {
                this.modal_imprimiendo.close();
            }
        }
    },

    async printXViaApi() {
        console.log("Imprimiendo Reporte X via API");
        this.modal_imprimiendo = Swal.fire({
            title: 'Imprimiendo',
            text: 'Por favor espere.',
            imageUrl: '/pos_fiscal_printer/static/src/image/impresora.gif',
            imageWidth: 100,
            imageHeight: 100,
            imageAlt: 'Imprimiendo',
            allowOutsideClick: false,
            allowEscapeKey: false,
            allowEnterKey: false,
            showConfirmButton: false,
            timer: 1500
        });
        var url = this.pos.config.api_url + "/xreport/print";
        try {
            const response = await fetch(url, {
                headers: {
                    'Bypass-Tunnel-Reminder': 'true'
                },
                credentials: 'include'
            });
            if (response.ok) {
                Swal.fire({
                    position: 'top-end',
                    icon: 'success',
                    title: 'Impresión finalizada con éxito',
                    showConfirmButton: false,
                    timer: 1500
                });
            } else {
                Swal.fire({
                    icon: 'error',
                    title: 'Error en impresión',
                    showConfirmButton: true,
                });
            }
        } catch (error) {
            console.error("Error en printXViaApi:", error);
            Swal.fire({
                icon: 'error',
                title: 'Error de conexión con la API',
                text: error.message,
                showConfirmButton: true,
            });
        } finally {
            if (this.modal_imprimiendo) {
                this.modal_imprimiendo.close();
            }
        }
    },

    async printViaApi() {
        console.log("Imprimiendo via API");
        this.modal_imprimiendo = Swal.fire({
            title: 'Imprimiendo',
            text: 'Por favor espere.',
            imageUrl: '/pos_fiscal_printer/static/src/image/impresora.gif',
            imageWidth: 100,
            imageHeight: 100,
            imageAlt: 'Imprimiendo',
            allowOutsideClick: false,
            allowEscapeKey: false,
            allowEnterKey: false,
            showConfirmButton: false,
        });

        const commands = this.printerCommands; // v52 - No mas map(sanitize) aqui
        console.warn("[FISCAL] printViaApi - Comandos a enviar:", commands);

        var body = JSON.stringify({
            params: {
                cmd: commands
            }
        });

        var url = this.pos.config.api_url + "/print_pos_ticket";

        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Bypass-Tunnel-Reminder': 'true'
                },
                body: body,
                credentials: 'include'
            });

            this.modal_imprimiendo.close();

            if (response.ok) {
                const data = await response.json();
                const result = data.result;

                if (result) {
                    console.warn("[FISCAL] printViaApi - Resultado de la API:", result);
                    if (result.state && result.state.lastInvoiceNumber) {
                        this.order.impresa = true;
                        console.log("Finalizada con factura " + result.state.lastInvoiceNumber.toString());
                        this.order.num_factura = result.state.lastInvoiceNumber.toString();

                        // Use this.pos.orm.call if available, or this.orm.call
                        const orm = this.orm || this.env?.services?.orm;
                        if (orm) {
                            await orm.call(
                                'pos.order',
                                'set_num_factura',
                                [this.order.id, this.order.name, this.order.num_factura]
                            );
                        }

                        Swal.fire({
                            position: 'top-end',
                            icon: 'success',
                            title: 'Impresión finalizada con éxito',
                            showConfirmButton: false,
                            timer: 1500
                        });
                    } else {
                        console.log("No hay numero de factura");
                        Swal.fire({
                            position: 'top-end',
                            icon: 'success',
                            title: 'Impresión finalizada con éxito y sin número de factura',
                            showConfirmButton: false,
                            timer: 1500
                        });
                    }
                } else {
                    Swal.fire({
                        icon: 'error',
                        title: 'Error en impresión',
                        text: (data.error && data.error.message) || 'Respuesta vacía',
                        showConfirmButton: true,
                    });
                }
            } else {
                Swal.fire({
                    icon: 'error',
                    title: 'Error en comunicación con la API: ' + response.status,
                    showConfirmButton: true,
                });
            }
        } catch (error) {
            this.modal_imprimiendo.close();
            console.error("Error en printViaApi:", error);
            Swal.fire({
                icon: 'error',
                title: 'Error al conectar con la API',
                text: error.message,
                showConfirmButton: true,
            });
        }
    },

    async read() {
        window.clearTimeout(this.timeout);
        // ... (read implementation kept to avoid large duplication but ensured presence)
        console.log("Leyendo", this.port.readable)
        while (this.port.readable) {
            console.log("Leyendo");
            try {
                while (true) {
                    const { value, done } = await this.reader.read();

                    if (done) {
                        console.log("Done");
                        break;
                    }

                    (value) && console.log(value);
                }
            } catch (error) {
                console.error(error);
            } finally {
                await Promise.all([
                    this.writer?.releaseLock(),
                    this.reader.releaseLock(),
                ]);
            }
        }

        this.printerCommands = [];
        this.reader.releaseLock();
        this.reader = false;
    },

    get order() {
        return this.props?.order || this.pos?.get_order?.() || this.pos?.currentOrder;
    },

    async doPrinting(mode) {
        if (!(this.order.payment_ids.every((p) => Boolean(p.payment_method_id?.x_printer_code)))) {
            console.warn("Algunos métodos de pago no tienen código de impresora, se usará '01' por defecto.");
        }
        if (this.order.impresa) {
            this.env.services.notification.add(_t("Documento impreso en máquina fiscal"), { type: "danger" });
            return;
        }
        this.printerCommands = [];
        switch (mode) {
            case "noFiscal":
                this.printNoFiscal();
                break;
            case "fiscal":
                this.read_s2 = true;
                this.printFiscal();
                break;
            case "notaCredito":
                this.read_s2 = true;
                const result = await this.printNotaCredito();
                if (!result) return;
                break;
        }

        if (this.pos.config.connection_type === "api") {
            await this.printViaApi();
        } else {
            await this.actionPrint();
        }
    },

    // Pachacutec: v108 - Labels ASCII y Truncado de Referencia
    setHeader(payload) {
        const order = this.pos.get_order();
        const client = order.partner;
        if (payload) {
            this.printerCommands.push("iF*" + payload.invoiceNumber.padStart(11, "0"));
            this.printerCommands.push("iD*" + payload.date);
            this.printerCommands.push("iI*" + payload.printerCode);
        }

        // v109: Sintonía de RIF (Sin Espacios). El espacio en 'No tiene' podría corromper la apertura.
        let vat = client?.vat || "Notiene";

        this.printerCommands.push("iR*" + sanitize(vat));
        this.printerCommands.push("iS*" + sanitize(client?.name || "CLIENTE GENERAL"));

        // v108: Forzamos labels ASCII en el código para evitar UTF-8 accidental en el buffer.
        this.printerCommands.push("i00Telefono: " + sanitize(client?.phone || "No tiene"));
        this.printerCommands.push("i01Direccion: " + sanitize(client?.street || "No tiene"));
        this.printerCommands.push("i02Email: " + sanitize(client?.email || "No tiene"));
        if (order.name) {
            this.printerCommands.push("i03Ref: " + sanitize(order.name).substring(0, 20));
        }

        console.warn("[FISCAL] v108 - Ráfaga de apertura (ASCII Pura) preparada.");
    },

    setTotal() {
        console.warn("[FISCAL] setTotal - Inicio");
        this.printerCommands.push("3"); // Subtotal

        const aplicar_igtf = this.pos.config.aplicar_igtf;
        const has_divisas = this.order.payment_ids.some(p => p.payment_method_id?.x_is_foreign_exchange);
        const use_igtf_closing = aplicar_igtf && has_divisas;

        const paymentlines = this.order.payment_ids;
        console.warn("[FISCAL] setTotal - Pagos:", paymentlines.length, "Cierre IGTF (199):", use_igtf_closing);
        
        const es_nota = this.order.lines.some((l) => Boolean(l.refunded_orderline_id));
        const active_payments = es_nota ? paymentlines.filter(p => p.amount < 0) : paymentlines.filter(p => p.amount > 0);

        active_payments.forEach((payment, i, array) => {
            const printer_code = payment.payment_method_id?.x_printer_code || '01';
            
            if ((i + 1) === array.length && array.length === 1) {
                // Pago Único (1 prefijo)
                console.warn("[FISCAL] v102 - Pago Único (Cierre):", "1" + printer_code);
                this.printerCommands.push("1" + printer_code);
            } else {
                // Pachacutec: v106 - Pago Parcial (Logic v16 convert split join)
                let amount_parts = convert(Math.abs(payment.amount), 2).split(",");
                amount_parts[0] = amount_parts[0].padStart(10, "0");
                let monto = amount_parts.join("");
                console.warn("[FISCAL] v106 - Pago Parcial (v16):", "2" + printer_code + monto);
                this.printerCommands.push("2" + printer_code + monto);
            }
        });

        // Pachacutec: v32 - El comando 199 CERRARÁ la factura si se detectaron divisas
        if (use_igtf_closing) {
            console.warn("[FISCAL] setTotal - Enviando cierre 199 (IGTF)");
            this.printerCommands.push("199");
        } else {
            // v59 - Cierre preventivo 101 solo si no hay un comando de cierre ya emitido
            const lastCmd = this.printerCommands[this.printerCommands.length - 1];
            const isClosing = lastCmd && lastCmd.startsWith("1") && lastCmd.length >= 3;
            if (!isClosing) {
                // v76 - Comando de cierre 101 sin padding (Trama Corta)
                this.printerCommands.push("101");
            }
        }

        console.warn("[FISCAL] setTotal - Comandos finales:", this.printerCommands);
    },

    printFiscal() {
        this.setHeader();
        this.setLines("GF");
        this.setTotal();
    },

    setLines(char) {
        console.warn("[FISCAL] setLines - Inicio con char:", char);
        this.order.lines
            .filter(line => !line.x_is_igtf_line)
            .forEach((line) => {
                // Pachacutec: v42 - Declaración de variables con ámbito correcto
                let tax_ids = [];
                let tax_records = [];

                try {
                    // Pachacutec: v41 - Resolución Ultra-Segura Odoo 18
                    const raw_taxes = line.tax_ids;
                    
                    if (raw_taxes) {
                        if (Array.isArray(raw_taxes)) {
                            tax_ids = raw_taxes.map(t => Number(typeof t === 'object' ? t.id : t));
                        } else if (raw_taxes.records) {
                            tax_ids = raw_taxes.records.map(r => Number(r.id));
                        } else if (typeof raw_taxes === 'object' && raw_taxes !== null) {
                            // Caso Proxy de record único o set
                            tax_ids = (raw_taxes.id) ? [Number(raw_taxes.id)] : [];
                        }
                    }

                    // Fallback a producto si tax_ids sigue vacío
                    if (tax_ids.length === 0 && line.product_id) {
                        const product = this.pos.models["product.product"]?.get(line.product_id.id || line.product_id);
                        const p_taxes = product?.taxes_id;
                        if (p_taxes) {
                            if (Array.isArray(p_taxes)) tax_ids = p_taxes.map(id => Number(id));
                            else if (p_taxes.records) tax_ids = p_taxes.records.map(r => Number(r.id));
                        }
                    }

                    // Limpieza e IDs únicos
                    tax_ids = [...new Set(tax_ids)].filter(id => id);
                    console.warn("[FISCAL] tax_ids normalizados (v42):", tax_ids);

                    // Resolver contra el modelo global de POS (DataStore en v18)
                    const tax_model = this.pos.models["account.tax"];
                    if (tax_model) {
                        // Pachacutec: v58 - Acceso Estricto a Modelo Reactivo Odoo 18
                        tax_records = tax_ids
                            .map(id => {
                                const rec = tax_model.get(id);
                                if (rec) {
                                    console.warn("[FISCAL] v58 - Impuesto Detectado:", id, " Amount:", rec.amount);
                                }
                                return rec;
                            })
                            .filter(t => t); 
                        
                        if (tax_records.length === 0) {
                            console.error("[FISCAL] v58 - FALLO CRÍTICO: No se hallaron impuestos para IDs:", tax_ids);
                            // Log de emergencia para depurar el DataStore
                            try {
                                const all_ids = tax_model.getAll().map(t => t.id);
                                console.warn("[FISCAL] v58 - IDs disponibles en account.tax:", all_ids.join(", "));
                            } catch(e) {}
                        }
                    } else {
                        console.error("[FISCAL] v58 - DataStore 'account.tax' NO EXISTE!");
                    }
                    
                } catch (e) {
                    console.error("[FISCAL] Error crítico en setLines v50:", e);
                }

                // Pachacutec: v41 - Determinación de Carácter Fiscal (Seguro Social)
                let tag = (char === "GC") ? "d0" : " "; // Default exento
                
                if (tax_records.length > 0) {
                    const first_tax = tax_records[0];
                    const type = first_tax.x_tipo_alicuota || first_tax.attr?.x_tipo_alicuota;
                    // v55 - Uso de amount como respaldo (IVA 16% es General)
                    const amount = first_tax.amount !== undefined ? first_tax.amount : (first_tax.attr?.amount || 0);

                    console.warn("[FISCAL] v55 - Analizando Tax:", {type, amount});

                    if (type === 'general' || amount === 16) tag = '!'; // v77: ! = 16% (General)
                    else if (type === 'reducido' || amount === 8 || amount === 12) tag = '"';
                    else if (type === 'adicional' || amount === 31) tag = '#';
                    else tag = ' '; // Espacio = Exento
                } 
                // Pachacutec: v56 - Failsafe: Si hay IDs pero no records, usar espacio (Exento) por seguridad
                else if (tax_ids.length > 0) {
                    console.warn("[FISCAL] v56 - Failsafe: IDs presentes pero records vacíos. Usando ' ' (Exento)");
                    tag = ' ';
                } else {
                    tag = ' '; // Exento
                }

                // Cálculo de precios y cantidades (v16 alignment)
                let unitPrice = line.get_unit_display_price ? line.get_unit_display_price() : (line.price_unit || 0);
                if (line.get_all_prices) {
                    const all_prices = line.get_all_prices();
                    unitPrice = all_prices.priceWithoutTaxBeforeDiscount / (line.qty || 1);
                }

                // Pachacutec: v106 - Sintonía de Padding Estructural v16 (10/8)
                // Usamos split/join sobre convert(toFixed) para blindar contra decimales flotantes.
                console.warn("[FISCAL] v106 - unitPrice original:", unitPrice);
                
                let price_parts = convert(unitPrice, 2).split(",");
                price_parts[0] = price_parts[0].padStart(8, "0");
                let price = price_parts.join("");

                let qty_val = Math.abs(line.qty || line.quantity || 0);
                let qty_parts = convert(qty_val, 3).split(",");
                qty_parts[0] = qty_parts[0].padStart(5, "0");
                let quantity = qty_parts.join("");
                
                // Pachacutec: v109 - Sintonía Radical (33 chars DATA = 36 bytes TOTAL)
                // Muchos firmwares HKA80 seriales rechazan tramas mayores a 36-40 bytes.
                const product = this.pos.models["product.product"]?.get(line.product_id?.id || line.product_id);
                const desc_clean = sanitize(line.full_product_name || product?.display_name || "PROD");
                const code_clean = sanitize(product?.default_code || "");
                
                let extra = "";
                if (code_clean) {
                    let code_trunc = code_clean.substring(0, 2);
                    // | (1) + code (2) + | (1) = 4 chars. Quedan 10 para name (Total 14 para extra).
                    let name_trunc = desc_clean.substring(0, 10);
                    extra = `|${code_trunc}|${name_trunc}`;
                } else {
                    // | (1) + desc (13) = 14. Total DATA 33 (19 + 14).
                    extra = `|${desc_clean.substring(0, 13)}`;
                }
                
                command += extra;
                console.warn(`[FISCAL] v109 - Línea (${command.length} chars DATA):`, command);
                this.printerCommands.push(command);

                if (line.discount > 0) {
                    let disc = line.discount.toFixed(2).replace(".", ",").replace(",", "").padStart(4, "0");
                    this.printerCommands.push("p-" + disc);
                }

                if (line.customer_note) {
                    this.printerCommands.push((char === "GC" ? "A##" : "@##") + sanitize(line.customer_note) + "##");
                }
            });
    },

    printNoFiscal() {
        this.order.lines
            .forEach((line) => {
                const name = cleanText(line.product_id?.display_name || "");
                const code = line.product_id?.default_code || "";
                this.printerCommands.push(`80 ${name} [${code}]`);
                this.printerCommands.push(`80*x${line.qty} ${(line.get_price_with_tax()).toFixed(2)}`);
            });

        if (this.order.amount_return) {
            this.printerCommands.push("80*CAMBIO: " + (this.order.amount_return).toFixed(2));
        }
        this.printerCommands.push("81$TOTAL: " + (this.order.get_total_with_tax()).toFixed(2));
    },

    async printNotaCredito() {
        const { confirmed, payload } = await this.env.services.dialog.add(NotaCreditoPopUp);
        if (!confirmed) return false;
        this.setHeader(payload);
        this.setLines("GC");
        this.setTotal();
        return true;
    },

    // Pachacutec: v103 - Diagnóstico de Status HKA80
    // Captura el estado interno de la impresora tras un fallo NAK.
    async fetchStatusDiagnosis() {
        console.warn("[FISCAL] v103 - Solicitando Diagnóstico de Status (S1)...");
        try {
            const cmdStatus = toBytes("S1");
            const writerStatus = this.port.writable.getWriter();
            await writerStatus.write(cmdStatus);
            await writerStatus.releaseLock();
            
            await new Promise(res => setTimeout(res, 300));
            
            const readerStatus = this.port.readable.getReader();
            const { value } = await readerStatus.read();
            console.warn("[FISCAL] v109 - RESPUESTA S1 (Uint8Array):", value);
            
            // Pachacutec: v109 - Decodificación Textual Forense
            try {
                const ascii_resp = Array.from(value).map(b => (b >= 32 && b <= 126) ? String.fromCharCode(b) : ".").join("");
                console.warn("[FISCAL] v109 - RESPUESTA S1 (ASCII):", ascii_resp);
            } catch(e) {}

            if (value && value.length >= 6) {
                // Pachacutec: v107 - Reparación de Índices Mandatoria
                // value[0]=STX, value[1]=S, value[2]=1. Los bytes de status reales empiezan en [3].
                console.warn("[FISCAL] Byte[1] (Status):", value[3].toString(2).padStart(8, '0'));
                console.warn("[FISCAL] Byte[2] (Error): ", value[4].toString(2).padStart(8, '0'));
                console.warn("[FISCAL] Byte[3] (Misc):  ", value[5].toString(2).padStart(8, '0'));
            }
            await readerStatus.releaseLock();
        } catch (e) {
            console.error("[FISCAL] v103 - Fallo en diagnóstico S1:", e);
        }
    }
};
