const encoder = new TextEncoder();
const cmd = "i03BARINAS";
const bytes = Array.from(encoder.encode(cmd));
const ETX = 3;
const STX = 2;

let lrc = STX; // v93 logic
for (const b of bytes) {
    lrc ^= b;
}
lrc ^= ETX;

console.log("Command:", cmd);
console.log("Bytes:", bytes);
console.log("LRC with STX (v93):", lrc);
