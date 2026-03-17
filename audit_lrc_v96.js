const STX = 2;
const ETX = 3;

function calculateLRC(data, includeSTX = true) {
    let lrc = includeSTX ? STX : 0;
    for (let i = 0; i < data.length; i++) {
        lrc ^= data[i];
    }
    lrc ^= ETX;
    return lrc;
}

// i03 from log: Uint8Array(34) [2, 105, ..., 3, 122]
const i03_data = new TextEncoder().encode("i03REF: ANIMAL CENTER - C3/0124");
console.log("i03 (Data + ETX):", calculateLRC(i03_data, false)); // Should be 122?
console.log("i03 (STX + Data + ETX):", calculateLRC(i03_data, true));

// ! from log: Uint8Array(46) [2, 33, ..., 3, 86]
const item_data = new TextEncoder().encode("!000005784000001000|PEZ-149|CARACOL MANZANA");
console.log("Item (Data + ETX):", calculateLRC(item_data, false));
console.log("Item (STX + Data + ETX):", calculateLRC(item_data, true)); // Should be 86?
