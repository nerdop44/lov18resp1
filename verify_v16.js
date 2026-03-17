const encoder = new TextEncoder();
const command = "!000005763800001000CARACOL MANZANA";

// v16 toBytes logic
function toBytesV16(cmd) {
    const commands = Array.from(encoder.encode(cmd));
    const ETX = 3;
    const STX = 2;

    commands.push(ETX);
    const lrc = commands.reduce((prev, curr) => prev ^ curr, 0);
    commands.push(lrc);
    commands.unshift(STX);

    return {
        bytes: commands,
        lrc: lrc,
        hexLrc: lrc.toString(16)
    };
}

const result = toBytesV16(command);
console.log("Command:", command);
console.log("Full Bytes:", result.bytes);
console.log("LRC (XOR of DATA + ETX):", result.lrc);
