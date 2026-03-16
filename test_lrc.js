const encoder = new TextEncoder();
const command = "!000005763800001000CARACOL MANZANA";
const dataBytes = Array.from(encoder.encode(command));
const etxtResult = [...dataBytes, 3].reduce((prev, curr) => prev ^ curr, 0);
console.log("DATA + ETX XOR (Should be 9):", etxtResult);

const stxResult = [2, ...dataBytes, 3].reduce((prev, curr) => prev ^ curr, 0);
console.log("STX + DATA + ETX XOR (Would be 11):", stxResult);
