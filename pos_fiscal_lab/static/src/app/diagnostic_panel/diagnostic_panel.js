/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class DiagnosticPanel extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            connected: false,
            logs: [],
            dbLogs: [], // Historial persistente del backend
            commands: [],
            selectedCommand: null,
            activeTemplate: null, // Guardará el JSON parseado
            dynamicFields: {},
            rawCommand: "",
            status: {
                b1_hex: "00", b1_bits: {},
                b2_hex: "00", b2_bits: {},
                b3_hex: "00", b3_bits: {},
                interpretation: ""
            }
        });

        this.port = null;
        this.writer = null;
        this.reader = null;

        onWillStart(async () => {
            await this.loadInitialData();
        });

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

    async loadInitialData() {
        this.state.commands = await this.orm.searchRead("pos.fiscal.command", [], ["name", "code", "field_template", "description"]);
        this.state.dbLogs = await this.orm.searchRead("pos.fiscal.log", [], ["timestamp", "command_raw", "response_raw", "interpretation"], { limit: 50, order: "timestamp desc" });
    }

    onCommandSelect(ev) {
        const cmdId = ev.target.value;
        const cmd = this.state.commands.find(c => c.id == cmdId);
        this.state.selectedCommand = cmd;
        this.state.dynamicFields = {};
        this.state.activeTemplate = null;
        if (cmd && cmd.field_template) {
            try {
                this.state.activeTemplate = JSON.parse(cmd.field_template);
                this.state.activeTemplate.fields.forEach(f => {
                    this.state.dynamicFields[f.name] = f.placeholder || "";
                });
            } catch (e) {
                console.error("Error parseando template", e);
                this.state.activeTemplate = null;
            }
        }
    }

    async connectPrinter() {
        try {
            this.port = await navigator.serial.requestPort();
            await this.port.open({ baudRate: 19200, parity: 'even' });
            this.state.connected = true;
            this.addLog("INFO", "Puerto abierto exitosamente.");
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
                    if (value) this.processResponse(value);
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
        
        let interpretation = this.interpretResponse(data);
        this.addLog("RECIBIDO", `Hex: ${hex} | Interpretación: ${interpretation}`);
        
        // Guardar en Backend
        this.saveLogToBackend(this.state.rawCommand, hex, interpretation);
    }

    interpretResponse(data) {
        if (data.length === 1) {
            if (data[0] === 0x06) return "ACK (Comando Aceptado)";
            if (data[0] === 0x15) return "NAK (Error de Protocolo o Estado)";
            if (data[0] === 0x04) return "EOT (Fin de Transmisión)";
        }

        let result = "Respuesta de Datos";
        if (data.length >= 6) {
            const b1 = data[3];
            const b2 = data[4];
            const b3 = data[5];
            this.updateStatusUI(b1, b2, b3);
            result += ` | B1:${b1.toString(16)} B2:${b2.toString(16)} B3:${b3.toString(16)}`;
            
            // Interpretación simple de errores críticos
            if (b2 & 0x01) result += " -> ERROR: Comando Inválido";
            if (b3 & 0x08) result += " -> BLOQUEO: Requiere Reporte Z";
            if (b1 & 0x04) result += " -> ADVERTENCIA: Sin Papel";
        }
        return result;
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

    async buildAndSend() {
        if (!this.state.selectedCommand) return;
        let cmd = this.state.selectedCommand.code;
        
        // Lógica de construcción dinámica
        if (this.state.selectedCommand.code === "!") {
             const tag = this.state.dynamicFields.tag || "!";
             const price = (this.state.dynamicFields.price || "0").padStart(12, "0");
             const qty = (this.state.dynamicFields.qty || "0").padStart(8, "0");
             const desc = (this.state.dynamicFields.desc || "").substring(0, 40);
             cmd = `!${price}${qty}|${desc}`; // Formato HKA Simplificado Lab
        } else if (this.state.selectedCommand.code === "i") {
             const type = this.state.dynamicFields.type || "0";
             const content = this.state.dynamicFields.content || "";
             cmd = `i${type}${content}`;
        }
        
        this.state.rawCommand = cmd;
        await this.sendRawCommand();
    }

    async sendRawCommand() {
        if (!this.port || !this.port.writable) return;
        const cmd = this.state.rawCommand;
        const frame = this.buildFrame(cmd);
        
        this.addLog("ENVIADO", `Trama Original: ${cmd}`);
        const writer = this.port.writable.getWriter();
        await writer.write(frame);
        writer.releaseLock();
    }

    buildFrame(cmd) {
        const encoder = new TextEncoder();
        const data = encoder.encode(cmd);
        const frame = new Uint8Array(data.length + 3);
        frame[0] = 0x02; // STX
        frame.set(data, 1);
        frame[frame.length - 2] = 0x03; // ETX
        
        let lrc = 0;
        for (let i = 1; i < frame.length - 1; i++) lrc ^= frame[i];
        frame[frame.length - 1] = lrc;
        return frame;
    }

    async saveLogToBackend(cmd, res, interp) {
        await this.orm.create("pos.fiscal.log", [{
            command_raw: cmd,
            response_raw: res,
            interpretation: interp,
            protocol: 'hka'
        }]);
        await this.loadInitialData(); // Refrescar historial
    }

    async clearHistory() {
        if (!confirm("¿Está seguro de vaciar todo el historial persistente?")) return;
        // En Odoo ORM, para borrar todos sin IDs a veces es mejor un rpc call o unlink con dominio grande
        const ids = this.state.dbLogs.map(l => l.id);
        if (ids.length > 0) {
            await this.orm.unlink("pos.fiscal.log", ids);
            this.addLog("INFO", "Historial del backend vaciado.");
            await this.loadInitialData();
        }
    }

    addLog(prefix, content) {
        const time = new Date().toLocaleTimeString();
        this.state.logs.push({ time, prefix, content, type: prefix.toLowerCase() });
        setTimeout(() => {
            const el = document.getElementById('lab_console');
            if (el) el.scrollTop = el.scrollHeight;
        }, 10);
    }
}

DiagnosticPanel.template = "pos_fiscal_lab.DiagnosticPanel";
registry.category("actions").add("pos_fiscal_lab.diagnostic_panel", DiagnosticPanel);
