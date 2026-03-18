/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

export class DiagnosticPanel extends Component {
    setup() {
        this.state = useState({
            connected: false,
            logs: [],
            rawCommand: "",
            status: {
                b1_hex: "00", b1_bits: {},
                b2_hex: "00", b2_bits: {},
                b3_hex: "00", b3_bits: {},
            }
        });

        this.port = null;
        this.writer = null;
        this.reader = null;

        // Mapeo Bit-a-Bit v3.6 (HKA)
        this.statusMapping = {
            b1: [
                { bit: 0, label: "Memoria Fiscal Llena" },
                { bit: 1, label: "Papel Cerca del Final" },
                { bit: 2, label: "Fin de Papel" },
                { bit: 3, label: "Modo Fiscal Activo" },
                { bit: 4, label: "Siempre 1 (Standard)" },
                { bit: 5, label: "Impresora Ocupada" },
                { bit: 6, label: "Fuera de Línea" },
                { bit: 7, label: "Error de Tapa" },
            ],
            b2: [
                { bit: 0, label: "Comando Inválido" },
                { bit: 1, label: "Error de Formato/Campo" },
                { bit: 2, label: "Error de Memoria de Trabajo" },
                { bit: 3, label: "Sin Memoria Fiscal" },
                { bit: 4, label: "Siempre 1" },
                { bit: 5, label: "Siempre 1" },
                { bit: 6, label: "Error de Reloj (RTC)" },
                { bit: 7, label: "Error de Comunicación DGI" },
            ],
            b3: [
                { bit: 0, label: "Documento Fiscal Abierto" },
                { bit: 1, label: "Tipo Doc (1=Fact, 0=NonFiscal)" },
                { bit: 2, label: "Slip Presente" },
                { bit: 3, label: "Reporte Z Requerido (+24h)" },
                { bit: 4, label: "Siempre 1" },
                { bit: 5, label: "Memoria de Auditoría Llena" },
                { bit: 6, label: "Siempre 1" },
                { bit: 7, label: "Reservado" },
            ]
        };
    }

    async connectPrinter() {
        try {
            this.port = await navigator.serial.requestPort();
            await this.port.open({ baudRate: 19200, parity: 'even' });
            this.state.connected = true;
            this.addLog("INFO", "Puerto abierto exitosamente a 19200 (Even).");
            this.listen();
        } catch (e) {
            this.addLog("ERROR", `Fallo al conectar: ${e.message}`);
        }
    }

    async listen() {
        while (this.port && this.port.readable) {
            this.reader = this.port.readable.getReader();
            try {
                while (true) {
                    const { value, done } = await this.reader.read();
                    if (done) break;
                    if (value) {
                        this.processResponse(value);
                    }
                }
            } catch (e) {
                this.addLog("ERROR", `Error en lectura: ${e.message}`);
            } finally {
                this.reader.releaseLock();
            }
        }
    }

    processResponse(data) {
        const hex = Array.from(data).map(b => b.toString(16).padStart(2, '0')).join(" ");
        const ascii = Array.from(data).map(b => (b >= 32 && b <= 126) ? String.fromCharCode(b) : ".").join("");
        this.addLog("RECIBIDO", `Hex: ${hex} | ASCII: ${ascii}`);

        // Intentar decodificar Status (HKA usualmente STX + DATA + Status1 + Status2 + Status3)
        // Detectamos si el frame contiene la respuesta S1-S6
        if (data.length >= 6) {
            // Buscamos el inicio de los bytes de status.
            // En HKA S1, suelen ser indices 3, 4, 5 si la respuesta es STX + "S1" + B1 + B2 + B3
            const b1 = data[3];
            const b2 = data[4];
            const b3 = data[5];
            this.updateStatusUI(b1, b2, b3);
        }
    }

    updateStatusUI(b1, b2, b3) {
        this.state.status.b1_hex = b1.toString(16).toUpperCase();
        this.state.status.b2_hex = b2.toString(16).toUpperCase();
        this.state.status.b3_hex = b3.toString(16).toUpperCase();

        for (let i = 0; i < 8; i++) {
            this.state.status.b1_bits[i] = !!(b1 & (1 << i));
            this.state.status.b2_bits[i] = !!(b2 & (1 << i));
            this.state.status.b3_bits[i] = !!(b3 & (1 << i));
        }
    }

    async sendCommand(cmdCode) {
        if (!this.state.connected) return alert("Conecte la impresora primero.");
        this.state.rawCommand = cmdCode;
        await this.sendRawCommand();
    }

    async sendRawCommand() {
        if (!this.port || !this.port.writable) return;
        const cmd = this.state.rawCommand;
        if (!cmd) return;

        // Construir trama: STX + CMD + ETX + LRC
        const encoder = new TextEncoder();
        const data = encoder.encode(cmd);
        const stx = 0x02;
        const etx = 0x03;
        
        const frame = new Uint8Array(data.length + 3);
        frame[0] = stx;
        frame.set(data, 1);
        frame[frame.length - 2] = etx;
        
        // Calcular LRC
        let lrc = 0;
        for (let i = 1; i < frame.length - 1; i++) {
            lrc ^= frame[i];
        }
        frame[frame.length - 1] = lrc;

        const hexFrame = Array.from(frame).map(b => b.toString(16).padStart(2, '0')).join(" ");
        this.addLog("ENVIADO", `Trama: ${hexFrame} (LRC: ${lrc.toString(16)})`);

        const writer = this.port.writable.getWriter();
        await writer.write(frame);
        writer.releaseLock();
    }

    addLog(prefix, content) {
        const time = new Date().toLocaleTimeString();
        this.state.logs.push({ time, prefix, content, type: prefix.toLowerCase() });
        // Auto-scroll
        setTimeout(() => {
            const el = document.getElementById('lab_console');
            if (el) el.scrollTop = el.scrollHeight;
        }, 10);
    }

    clearConsole() {
        this.state.logs = [];
    }
}

DiagnosticPanel.template = "pos_fiscal_lab.DiagnosticPanel";
registry.category("actions").add("pos_fiscal_lab.diagnostic_panel", DiagnosticPanel);
