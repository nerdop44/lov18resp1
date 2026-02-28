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

export function sanitize(string) {
    return string.replace(EXPRESSION, (char) => CHAR_MAP[char]);
}

export function toBytes(command) {
    const commands = Array.from(encoder.encode(command));
    commands.push(3);
    commands.push(commands.reduce((prev, curr) => prev ^ curr, 0));
    commands.unshift(2);
    return new Uint8Array(commands);
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

                const parity = this.pos.config.x_fiscal_command_parity || "even";
                const baudRate = parseInt(this.pos.config.x_fiscal_command_baudrate) || 9600;
                console.log("Configurando puerto - BaudRate:", baudRate, "Paridad:", parity);

                try {
                    await port.open({
                        baudRate: baudRate,
                        parity: parity,
                        dataBits: 8,
                        stopBits: 1,
                    });
                    console.log("Puerto abierto exitosamente.");
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

    async escribe_leer(command, is_linea) {
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
            while (leer) {
                try {
                    const { value, done } = await this.reader.read();
                    if (value.byteLength >= 1) {
                        console.log("Respuesta de comando: ");
                        console.log(value);
                        console.log("Respuesta detallada: ");
                        console.log(value[0]);
                        if (true) {
                            if (value[0] == 6) {
                                leer = false;
                                console.log("Finalizanda lectura");
                                console.log("comando aceptado");
                                await this.reader.releaseLock();
                                this.reader = false;

                                return true;
                            } else {
                                console.log("Comando no reconocido");
                                leer = false;
                                await this.reader.releaseLock();
                                this.reader = false;
                                await new Promise(
                                    (res) => setTimeout(() => res(), 100)
                                );
                                this.writer = this.port.writable.getWriter();
                                var comando_desbloqueo = ["7"];
                                var comando_desbloqueo = comando_desbloqueo.map(toBytes);
                                for (const command of comando_desbloqueo) {
                                    await new Promise(
                                        (res) => setTimeout(() => res(this.writer.write(command)), 150)
                                    );
                                }
                                await this.writer.releaseLock();
                                this.writer = false;
                                this.printing = false;
                                return true;
                            }
                        } else {
                            leer = false;
                            console.log("Finalizanda lectura");
                            console.log("comando aceptado");
                            await this.reader.releaseLock();
                            this.reader = false;

                            return true;
                        }

                    } else {
                        console.log("No hay datos");
                        //esperar 150ms
                        esperando++;
                        await new Promise(
                            (res) => setTimeout(() => res(), 200)
                        );
                    }
                    if (esperando > 20) {
                        await this.reader.releaseLock();
                        this.reader = false;
                        var comando_desbloqueo = ["7"];
                        var comando_desbloqueo = comando_desbloqueo.map(toBytes);
                        this.writer = this.port.writable.getWriter();
                        for (const command of comando_desbloqueo) {
                            await new Promise(
                                (res) => setTimeout(() => res(this.writer.write(command)), 150)
                            );
                        }
                        await this.writer.releaseLock();
                        this.writer = false;
                        this.printing = false;
                        return true;
                    }
                } catch (error) {
                    console.log("Error al leer puerto");
                    console.error(error);
                    leer = false;
                    var comando_desbloqueo = ["7"];
                    var comando_desbloqueo_cod = comando_desbloqueo.map(toBytes);
                    // No release here as it's finally handled
                    return false;
                } finally {
                    if (this.reader) {
                        try {
                            await this.reader.releaseLock();
                        } catch (e) { console.warn("Error releasing reader lock:", e); }
                        this.reader = false;
                    }
                    if (this.writer) {
                        try {
                            await this.writer.releaseLock();
                        } catch (e) { console.warn("Error releasing writer lock:", e); }
                        this.writer = false;
                    }
                }
            }
        } else {
            console.log("Error signals CTS: ", signals);
            await this.writer.releaseLock();
            this.writer = false;
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


        const TIME = this.pos.config.x_fiscal_commands_time || 750;
        this.printing = true;
        this.printerCommands = this.printerCommands.map(sanitize);
        console.log("Comandos: ", this.printerCommands);
        var cantidad_comandos = this.printerCommands.length;
        for (const command of this.printerCommands) {
            var is_linea = false;
            if (command.substring(0, 1) === ' ' || command.substring(0, 1) === '!' || command.substring(0, 1) === 'd' || command.substring(0, 1) === '-') {
                is_linea = true;
            }
            if (this.printing) {
                await new Promise(
                    (res) => setTimeout(() => res(this.escribe_leer(command, is_linea)), TIME)
                );
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
        for (const command in this.printerCommands) {
            await new Promise(
                (res) => setTimeout(() => res(this.writer.write(this.printerCommands[command])), TIME)
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
                        console.log(value);
                        var string = new TextDecoder().decode(value);
                        console.log(string);
                        if (string.length > 0) {
                            const myArray = string.split('\n');
                            var num_factura = myArray[2];
                            if (num_factura) {
                                console.log("Numero de factura: ", num_factura);
                                this.order.num_factura = num_factura;
                                this.reader.releaseLock();
                                this.reader = false;
                                leer = false;
                                break;
                            } else {
                                contador++;
                                await new Promise(
                                    (res) => setTimeout(() => res(), 150)
                                );
                                if (contador > 10) {
                                    this.reader.releaseLock();
                                    this.reader = false;
                                    leer = false;
                                    break;
                                    console.log("Error al leer numero de factura");
                                }
                            }
                        } else {
                            contador++;
                            await new Promise(
                                (res) => setTimeout(() => res(), 150)
                            );
                            if (contador > 10) {
                                this.reader.releaseLock();
                                this.reader = false;
                                leer = false;
                                break;
                                console.log("Error al leer numero de factura");
                            }
                        }
                    }
                } catch (error) {
                    leer = false;
                    console.error("Error en lectura write_s2:", error);
                } finally {
                    if (this.reader) {
                        try {
                            this.reader.releaseLock();
                        } catch (e) { }
                        this.reader = false;
                    }
                    leer = false;
                }
            }
            await this.orm.call(
                'pos.order',
                'set_num_factura',
                [this.order.id, this.order.name, this.order.num_factura]
            );

        }

        this.printerCommands = [];
        this.read_s2 = false;
    },

    async write_Z() {
        this.read_Z = true;
        this.writer = this.port.writable.getWriter();
        const TIME = this.pos.config.x_fiscal_commands_time || 750;
        this.printerCommands = ["U4z02002230200223"];
        this.printerCommands = this.printerCommands.map(toBytes);
        console.log("Escribiendo U4z02002230200223", this.printerCommands);
        for (const command in this.printerCommands) {
            await new Promise(
                (res) => setTimeout(() => res(this.writer.write(this.printerCommands[command])), TIME)
            );
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
        } else {
            const result = await this.setPort();
            if (!result) return;
            this.write();
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

        const commands = this.printerCommands.map(sanitize);
        console.log("Comandos sanitizados:", commands);

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
        return this.pos.get_order();
    },

    async doPrinting(mode) {
        if (!(this.order.payment_ids.every((p) => Boolean(p.payment_method_id?.x_printer_code)))) {
            this.env.services.notification.add(_t("Algunos métodos de pago no tienen código de impresora"), { type: "danger" });
            return;
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

    setHeader(payload) {
        const client = this.order.partner_id || {};
        if (payload) {
            this.printerCommands.push("iF*" + payload.invoiceNumber.padStart(11, "0"));
            this.printerCommands.push("iD*" + payload.date);
            this.printerCommands.push("iI*" + payload.printerCode);
        }

        this.printerCommands.push("iR*" + (client.vat || "No tiene"));
        this.printerCommands.push("iS*" + sanitize(client.name || "Cliente Contado"));

        this.printerCommands.push("i00Teléfono: " + (client.phone || "No tiene"));
        this.printerCommands.push("i01Dirección: " + sanitize(client.street || "No tiene"));
        this.printerCommands.push("i02Email: " + (client.email || "No tiene"));
        if (this.order.pos_reference) {
            this.printerCommands.push("i03Ref: " + this.order.pos_reference);
        }
    },

    setTotal() {
        this.printerCommands.push("3");
        const aplicar_igtf = this.pos.config.aplicar_igtf;
        const es_nota = this.order.lines.some((l) => Boolean(l.refunded_orderline_id));

        const paymentlines = this.order.payment_ids;
        if (es_nota) {
            if (paymentlines.filter((p) => p.amount < 0).every((p) => p.isForeignExchange) && aplicar_igtf) {
                this.printerCommands.push("122");
            } else {
                paymentlines.filter((p) => p.amount < 0).forEach((payment, i, array) => {
                    const printer_code = payment.payment_method_id?.x_printer_code;
                    if ((i + 1) === array.length && array.length === 1) {
                        this.printerCommands.push("1" + printer_code);
                    } else {
                        let amountStr = (Math.abs(payment.amount) || 0).toFixed(2).replace(".", ",");
                        let [entero, decimal] = amountStr.split(",");
                        entero = this.pos.config.flag_21 === '30' ? entero.padStart(15, "0") : entero.padStart(10, "0");
                        this.printerCommands.push("2" + printer_code + entero + decimal);
                    }
                });
            }
        } else {
            if (paymentlines.filter((p) => p.amount > 0).every((p) => p.isForeignExchange) && aplicar_igtf) {
                this.printerCommands.push("122");
            } else {
                paymentlines.filter((p) => p.amount > 0).forEach((payment, i, array) => {
                    const printer_code = payment.payment_method_id?.x_printer_code;
                    if ((i + 1) === array.length && array.length === 1) {
                        this.printerCommands.push("1" + printer_code);
                    } else {
                        let amountStr = (Math.abs(payment.amount) || 0).toFixed(2).replace(".", ",");
                        let [entero, decimal] = amountStr.split(",");
                        entero = this.pos.config.flag_21 === '30' ? entero.padStart(15, "0") : entero.padStart(10, "0");
                        this.printerCommands.push("2" + printer_code + entero + decimal);
                    }
                });
            }
        }

        if (aplicar_igtf) {
            this.printerCommands.push("199");
        } else {
            if (this.printerCommands[this.printerCommands.length - 1] !== '101') {
                this.printerCommands.push("101");
            }
        }
    },

    printFiscal() {
        this.setHeader();
        this.setLines("GF");
        this.setTotal();
    },

    setLines(char) {
        this.order.lines
            .filter((l) => !l.x_is_igtf_line)
            .forEach((line) => {
                let command = "";
                const taxes = line.tax_ids || [];

                if (!(taxes.length) || taxes.every((t) => (t.x_tipo_alicuota || "exento") === "exento")) {
                    command += (char === "GC") ? "d0" : " ";
                } else if (taxes.every((t) => t.x_tipo_alicuota === "general")) {
                    command += (char === "GC") ? "d1" : "!";
                } else {
                    command += (char === "GC") ? "d0" : " ";
                }

                let price = (line.get_price_without_tax() / line.qty).toFixed(2).replace(".", ",");
                if (line.discount > 0) {
                    price = (line.get_all_prices(1).priceWithoutTaxBeforeDiscount).toFixed(2).replace(".", ",");
                }
                let qty = (Math.abs(line.qty)).toFixed(3).replace(".", ",");

                let [pEnt, pDec] = price.split(",");
                let [qEnt, qDec] = qty.split(",");

                pEnt = this.pos.config.flag_21 === '30' ? pEnt.padStart(14, "0") : pEnt.padStart(8, "0");
                qEnt = this.pos.config.flag_21 === '30' ? qEnt.padStart(14, "0") : qEnt.padStart(5, "0");

                command += pEnt + pDec + qEnt + qDec;

                if (line.product_id?.default_code) {
                    command += `|${line.product_id.default_code}|`;
                }

                command += sanitize(line.product_id?.display_name || "");
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
            .filter((l) => !l.x_is_igtf_line)
            .forEach((line) => {
                const name = sanitize(line.product_id?.display_name || "");
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
    }
};
