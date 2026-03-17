const encoder = new TextEncoder();
const tax = "!";
const price = "0000057638";
const qty = "00001000";
const code = "0001"; // Generic code
const name = "CARACOL MANZANA";

function calcLRC(data) {
    const bytes = Array.from(encoder.encode(data));
    const ETX = 3;
    let lrc = 0;
    for (const b of bytes) lrc ^= b;
    lrc ^= ETX;
    return lrc;
}

const tramaV18 = tax + price + qty + name;
const tramaV16 = tax + price + qty + "|" + code + "|" + name;

console.log("DATA V18:", tramaV18);
console.log("LRC V18 (DATA^ETX):", calcLRC(tramaV18)); // Expect 11

console.log("DATA V16 (with pipes):", tramaV16);
console.log("LRC V16 (DATA^ETX):", calcLRC(tramaV16));
