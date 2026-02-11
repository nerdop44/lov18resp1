import tkinter as tk
from tkinter import scrolledtext, ttk
import threading
import os
import pty
import datetime
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

class FiscalAPIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Redirect standard server logs to emulator technical log
        message = format % args
        self.server.emulator.log(f"HTTP: {message}")

    def do_OPTIONS(self):
        self.server.emulator.log(f">>> RECIBIDO OPTIONS: {self.path}")
        for header, value in self.headers.items():
             self.server.emulator.log(f"    {header}: {value}")
             
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Access-Control-Allow-Private-Network, X-Requested-With')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.end_headers()
        self.server.emulator.log("<<< ENVIADO 204 OPTIONS (CORS/PNA OK)")

    def do_GET(self):
        self.server.emulator.log(f">>> RECIBIDO GET: {self.path}")
        if self.path == '/xreport/print':
            self.server.emulator.queue_command("I0X")
            self._send_response({"status": "success", "message": "Reporte X enviado"})
        elif self.path == '/zreport/print':
            self.server.emulator.queue_command("I0Z")
            self._send_response({"status": "success", "message": "Reporte Z enviado"})
        else:
            self.send_error(404)

    def do_POST(self):
        self.server.emulator.log(f">>> RECIBIDO POST: {self.path}")
        if self.path == '/print_pos_ticket':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                cmds = data.get('cmd') or data.get('params', {}).get('cmd', [])
                self.server.emulator.log(f"    Comandos recibidos: {len(cmds)}")
                for cmd in cmds:
                    self.server.emulator.queue_command(cmd)
                
                inv_num = self.server.emulator.ent_invoice.get()
                self._send_response({
                    "result": True,
                    "state": {"lastInvoiceNumber": inv_num}
                })
            except Exception as e:
                self.server.emulator.log(f"    ERROR POST: {e}")
                self.send_error(400, str(e))
        else:
            self.send_error(404)

    def _send_response(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
        self.server.emulator.log(f"<<< ENVIADO 200 OK: {self.path}")

class FiscalPrinterEmulator:
    def __init__(self, root):
        self.root = root
        self.root.title("Emulador Impresora Fiscal (HKA80/DT230) - Visual - Ing Nerdo Pulido")
        self.root.geometry("900x600")

        self.serial_port = None
        self.running = False
        self.master_fd = None
        self.slave_name = None
        
        # Command Parsing Buffer
        self.buffer = b""

        self.create_widgets()
        self.start_api_server()

    def start_api_server(self):
        def run_server():
            server_address = ('', 5000)
            self.httpd = HTTPServer(server_address, FiscalAPIHandler)
            self.httpd.server = self
            self.log("--- API HTTP INICIADA EN PUERTO 5000 ---")
            self.httpd.serve_forever()

        self.api_thread = threading.Thread(target=run_server)
        self.api_thread.daemon = True
        self.api_thread.start()

    def queue_command(self, cmd):
        """Thread-safe way to queue command execution in the main UI thread"""
        self.root.after(0, self.execute_api_command, cmd)

    def execute_api_command(self, cmd):
        self.log(f"API: {cmd}", "cmd")
        self.interpret_command(cmd)

    def create_widgets(self):
        # Top Config Frame
        frame_top = tk.Frame(self.root, pady=10)
        frame_top.pack(fill=tk.X, padx=10)

        # Status Section
        frame_status = tk.LabelFrame(frame_top, text="Estado de Conexión Serial", padx=10, pady=5)
        frame_status.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        self.lbl_status = tk.Label(frame_status, text="DESCONECTADO", fg="red", font=("Arial", 12, "bold"))
        self.lbl_status.pack(side=tk.LEFT)
        
        self.lbl_port = tk.Label(frame_status, text="Puerto: -", fg="blue")
        self.lbl_port.pack(side=tk.LEFT, padx=10)

        self.btn_start = tk.Button(frame_status, text="ACTIVAR SERIAL", command=self.start_emulation, bg="#4CAF50", fg="white", width=12)
        self.btn_start.pack(side=tk.LEFT, padx=5)
        
        self.btn_stop = tk.Button(frame_status, text="PARAR SERIAL", command=self.stop_emulation, state=tk.DISABLED, bg="#f44336", fg="white", width=12)
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        # Configuration Section
        frame_config = tk.LabelFrame(frame_top, text="Configuración Fiscal / API", padx=10, pady=5)
        frame_config.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        tk.Label(frame_config, text="Próxima Factura:").pack(side=tk.LEFT)
        self.ent_invoice = tk.Entry(frame_config, width=10, font=("Consolas", 10))
        self.ent_invoice.insert(0, "00000001")
        self.ent_invoice.pack(side=tk.LEFT, padx=5)
        
        tk.Label(frame_config, text="API: http://localhost:5000", fg="gray60").pack(side=tk.LEFT, padx=10)

        # Main Content Area (Split Panes)
        paned_window = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left Panel: Hex Log (Technical)
        frame_left = tk.Frame(paned_window)
        tk.Label(frame_left, text="Registro Técnico (API/Serial/Comandos)", font=("Arial", 9, "bold")).pack(anchor="w")
        self.txt_log = scrolledtext.ScrolledText(frame_left, width=40, height=20, font=("Consolas", 8), bg="#f0f0f0")
        self.txt_log.pack(fill=tk.BOTH, expand=True)
        paned_window.add(frame_left)

        # Right Panel: Visual Receipt (User Friendly)
        frame_right = tk.Frame(paned_window, bg="white", highlightbackground="#888", highlightthickness=1)
        tk.Label(frame_right, text="Vista Previa de Impresión (Papel)", font=("Arial", 9, "bold"), bg="white").pack(anchor="w", padx=5, pady=5)
        
        self.txt_receipt = scrolledtext.ScrolledText(frame_right, width=40, height=20, font=("Courier New", 10, "bold"), bg="#fffbe6") # Pastel yellow paper look
        self.txt_receipt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Add paper cut button
        tk.Button(frame_right, text="Cortar / Limpiar Papel", command=self.clear_receipt).pack(anchor="e", padx=10, pady=5)

        paned_window.add(frame_right)

    def log(self, message, tag=None):
        def _log():
            self.txt_log.config(state='normal')
            self.txt_log.insert(tk.END, message + "\n", tag)
            self.txt_log.see(tk.END)
            self.txt_log.config(state='disabled')
        # Ensure UI update happens in main thread
        self.root.after(0, _log)

    def print_line(self, text):
        """Prints a visual line to the 'paper' receipt"""
        def _print():
            self.txt_receipt.config(state='normal')
            self.txt_receipt.insert(tk.END, text + "\n")
            self.txt_receipt.see(tk.END)
            self.txt_receipt.config(state='disabled')
        self.root.after(0, _print)
        
    def clear_receipt(self):
        self.txt_receipt.config(state='normal')
        self.txt_receipt.delete('1.0', tk.END)
        self.txt_receipt.config(state='disabled')

    def start_emulation(self):
        try:
            self.master_fd, slave_fd = pty.openpty()
            self.slave_name = os.ttyname(slave_fd)
            
            self.lbl_port.config(text=f"Puerto: {self.slave_name}")
            self.lbl_status.config(text="ESCUCHANDO", fg="green")
            
            self.running = True
            self.btn_start.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
            self.buffer = b""

            self.thread = threading.Thread(target=self.read_loop)
            self.thread.daemon = True
            self.thread.start()
            
            self.log(f"--- SERIAL INICIADO EN {self.slave_name} ---")
            
        except Exception as e:
            self.log(f"Error: {e}")

    def stop_emulation(self):
        self.running = False
        if self.master_fd:
            os.close(self.master_fd)
            self.master_fd = None
            
        self.lbl_status.config(text="DESCONECTADO", fg="red")
        self.lbl_port.config(text="Puerto: -")
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.log("--- SERIAL DETENIDO ---")

    def read_loop(self):
        while self.running and self.master_fd:
            try:
                data = os.read(self.master_fd, 1024)
                if data:
                    self.process_data(data)
            except OSError:
                break
                
    def process_data(self, data):
        # Determine protocol
        # STX (0x02) + CMD + DATA + ETX(0x03) + LRC
        
        self.buffer += data
        
        while b'\x02' in self.buffer:
            start_index = self.buffer.find(b'\x02')
            if start_index > 0:
                self.buffer = self.buffer[start_index:] # Trim garbage
                
            # Check if we have ETX
            if b'\x03' in self.buffer:
                end_index = self.buffer.find(b'\x03') + 1 # Include ETX
                if end_index + 1 <= len(self.buffer): # +1 for LRC byte
                    packet = self.buffer[:end_index+1]
                    self.buffer = self.buffer[end_index+1:]
                    self.parse_packet(packet)
                else:
                    break # Wait for LRC
            else:
                break # Wait for ETX

    def parse_packet(self, packet):
        try:
            # Packet: STX (1) | CMD/DATA (N) | ETX (1) | LRC (1)
            payload = packet[1:-2].decode('utf-8', errors='ignore')
            self.log(f"RCV SERIAL: {payload}", "cmd")
            self.interpret_command(payload)
            self.send_ack()
        except Exception as e:
            self.log(f"Parse Error: {e}")

    def interpret_command(self, cmd):
        """Interprets HKA/Bixolon protocol strings"""
        
        # --- HEADERS ---
        if cmd.startswith("iS*"):
            client_name = cmd[3:]
            self.print_line("----------------------------------------")
            self.print_line(f"CLIENTE: {client_name}")
            
        elif cmd.startswith("iR*"):
            rif = cmd[3:]
            self.print_line(f"RIF:     {rif}")
            
        elif cmd.startswith("i01"):
            addr = cmd[3:]
            self.print_line(f"DIR:     {addr}")

        # --- ITEMS ---
        elif cmd.startswith(" ") or cmd.startswith("!"):
            try:
                price_str = cmd[1:11]
                qty_str = cmd[11:16]
                name = cmd[16:].replace("|", "")
                
                price = float(price_str) / 100
                qty = float(qty_str) / 1000
                total = price * qty
                
                self.print_line(f"{name[:20].ljust(20)} {qty:.2f} x {price:.2f}")
                self.print_line(f"{' ' * 25} {total:.2f}")
            except:
                self.print_line(f"ITEM: {cmd}")

        elif cmd.startswith("3"):
            self.print_line("----------------------------------------")
            self.print_line(f"SUBTOTAL CAJA")

        elif cmd.startswith("101"):
            self.print_line(f"TOTAL A PAGAR")
            self.print_line("========================================")
            # Trigger invoice number generation
            inv_num = self.ent_invoice.get()
            self.print_line(f"FACTURA FISCAL N°: {inv_num}")
            self.print_line(f"FECHA: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}")
            self.print_line("\n\n")
            self.increment_invoice()

        # --- REPORTS ---
        elif cmd.startswith("U4") or cmd.startswith("I0Z"): # I0Z used in POS API/Direct
             self.print_line("\n\n*** REPORTE Z ***")
             self.print_line(f"Z N°: {datetime.datetime.now().strftime('%Y%m%d')}")
             self.print_line("TOTAL VENTAS FISCALES: $$$")
             self.print_line("*****************\n")

        elif cmd.startswith("I0X"):
             self.print_line("\n\n*** REPORTE X ***")
             self.print_line("TOTAL VENTAS HASTA AHORA: $$$")
             self.print_line("*****************\n")

        elif "S1" in cmd:
            self.log("Consulta de Estado (S1)")
            self.send_status_response()
            return

    def increment_invoice(self):
        try:
             inv = self.ent_invoice.get()
             next_inv = int(inv) + 1
             def _inc():
                 self.ent_invoice.delete(0, tk.END)
                 self.ent_invoice.insert(0, str(next_inv).zfill(8))
             self.root.after(0, _inc)
        except: pass

    def send_ack(self):
        if self.master_fd:
            os.write(self.master_fd, b'\x06')

    def send_status_response(self):
        inv = self.ent_invoice.get().zfill(8)
        response = f"OK\nSTATUS\n{inv}\n"
        if self.master_fd:
            os.write(self.master_fd, response.encode('utf-8'))

if __name__ == "__main__":
    root = tk.Tk()
    app = FiscalPrinterEmulator(root)
    root.mainloop()
