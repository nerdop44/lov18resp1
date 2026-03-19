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
        this.buffer = new Uint8Array(0); // Búfer de reconstrucción

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
        // Concatenar al búfer existente
        let newBuffer = new Uint8Array(this.buffer.length + data.length);
        newBuffer.set(this.buffer);
        newBuffer.set(data, this.buffer.length);
        this.buffer = newBuffer;

        // Buscar tramas completas
        this.findAndProcessFrames();
    }

    findAndProcessFrames() {
        let stxIdx = this.buffer.indexOf(0x02);
        let etxIdx = this.buffer.indexOf(0x03);

        // Caso especial: ACK/NAK/EOT son un solo byte y no tienen STX/ETX
        if (this.buffer.length === 1 && [0x06, 0x15, 0x04].includes(this.buffer[0])) {
            const byte = this.buffer[0];
            const interp = this.interpretControlByte(byte);
            this.addLog("RECIBIDO", `Byte: ${byte.toString(16).padStart(2, '0')} | ${interp}`);
            this.saveLogToBackend(this.state.rawCommand, byte.toString(16).padStart(2, '0'), interp);
            this.buffer = new Uint8Array(0);
            return;
        }

        if (stxIdx !== -1 && etxIdx !== -1 && etxIdx > stxIdx) {
            // Trama completa detectada
            const frame = this.buffer.slice(stxIdx, etxIdx + 2); // STX ... ETX + LRC
            this.handleFullFrame(frame);
            
            // Limpiar búfer hasta después del ETX + LRC
            this.buffer = this.buffer.slice(etxIdx + 2);
            
            // Buscar si hay más tramas en lo que queda
            if (this.buffer.length > 0) this.findAndProcessFrames();
        }
    }

    interpretControlByte(byte) {
        if (byte === 0x06) return "ACK (Comando Aceptado)";
        if (byte === 0x15) return "NAK (Error de Protocolo o Estado)";
        if (byte === 0x04) return "EOT (Fin de Transmisión)";
        return "Byte Desconocido";
    }

    handleFullFrame(frame) {
        const hex = Array.from(frame).map(b => b.toString(16).padStart(2, '0')).join(" ");
        let interp = "Trama de Datos";
        let dataStart = 1; // Salto STX

        // Auto-Detección de Eco: Si los primeros bytes coinciden con el comando enviado (p.ej. S1)
        const decoder = new TextDecoder();
        const possibleEcho = decoder.decode(frame.slice(1, 3));
        if (possibleEcho === this.state.rawCommand || possibleEcho === "S1" || possibleEcho === "S2") {
            dataStart = 3; // Saltamos STX + Eco (2 bytes)
        }

        if (frame.length >= dataStart + 3) {
            const b1 = frame[dataStart];
            const b2 = frame[dataStart + 1];
            const b3 = frame[dataStart + 2];
            this.updateStatusUI(b1, b2, b3);
            
            const dataBytes = frame.slice(dataStart + 3, frame.length - 2);
            const ascii = decoder.decode(dataBytes);
            interp = `Status[${b1.toString(16)},${b2.toString(16)},${b3.toString(16)}]`;
            
            if (ascii.includes("\n")) {
                const fields = ascii.split("\n");
                interp += ` | ${fields.length} campos detectados.`;
                const serial = fields.find(f => f.match(/^[Z][0-9A-Z]{9}$/));
                const rif = fields.find(f => f.match(/^[JEGVPV][\-0-9]{8,12}$/));
                if (serial) interp += ` -> Serial: ${serial}`;
                if (rif) interp += ` -> RIF: ${rif}`;
                
                // Log detallado de campos para la consola (Pachacutec)
                fields.forEach((f, i) => {
                    if (f.trim()) this.addLog("CAMPO", `[${i+1}] ${f}`);
                });
            }
        }

        this.addLog("RECIBIDO", `Hex: ${hex} | Interpretación: ${interp}`);
        this.saveLogToBackend(this.state.rawCommand, hex, interp);
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

    async sendCommand(cmdCode) {
        this.state.rawCommand = cmdCode;
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
