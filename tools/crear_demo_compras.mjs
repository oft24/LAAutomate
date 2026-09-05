import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const output = path.resolve('outputs/demo-compras');
await fs.mkdir(output, { recursive: true });
const file = path.join(output, 'productos.xlsx');
try { await fs.access(file); throw new Error('productos.xlsx ya existe; no se sobrescribe tu lista.'); }
catch (error) { if (error.code !== 'ENOENT') throw error; }
const wb = Workbook.create();
const sheet = wb.worksheets.add('Productos');
sheet.getRange('A1:D3').values = [
 ['SKU', 'Cantidad', 'Activo', 'Descripción'],
 ['MON-24', 1, 'Sí', 'Monitor Claro 24 FHD'],
 ['TEC-01', 2, 'Sí', 'Teclado Claro USB'],
];
sheet.getRange('A1:D20').format.font = {name:'Arial',size:11,color:'#192B3B'};
sheet.getRange('A1:D1').format = {fill:'#15283C',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},rowHeight:30};
sheet.getRange('A2:D20').format.rowHeight = 25;
sheet.getRange('A:A').format.columnWidth = 18;
sheet.getRange('B:C').format.columnWidth = 15;
sheet.getRange('D:D').format.columnWidth = 34;
sheet.getRange('B2:B1000').setNumberFormat('0');
sheet.getRange('B2:B1000').dataValidation = {rule:{type:'whole',operator:'greaterThan',formula1:0}};
sheet.getRange('C2:C1000').dataValidation = {rule:{type:'list',values:['Sí','No']}};
sheet.tables.add('A1:D3', true, 'ProductosEntrada');
sheet.freezePanes.freezeRows(1);
sheet.showGridLines = false;
const guia = wb.worksheets.add('Guía');
guia.getRange('A1:B9').values = [
 ['Comparativo de compras', 'Demostración con datos ficticios'],
 ['Uso', 'Edita la hoja Productos, guarda y cierra el archivo antes de ejecutar.'],
 ['Agregar una solicitud', 'Añade una fila: MOU-01 | 3 | Sí | Mouse Claro inalámbrico.'],
 ['Catálogo de prueba', 'MON-24, TEC-01, MOU-01 y CAM-01. Otros códigos producen Sin resultados.'],
 ['Cantidad', 'Entero positivo. El stock debe cubrir todas las unidades.'],
 ['Cálculo', 'Total = precio unitario × cantidad + un envío por pedido y producto.'],
 ['Disponibilidad', 'CAM-01 permite probar ofertas sin existencias. No debe tener ganador.'],
 ['Alcance', 'No compra ni envía mensajes. No consulta precios de tiendas reales.'],
 ['Resultado', 'Cada ejecución crea un reporte nuevo; no modifica tu lista de entrada.'],
];
guia.getRange('A1:B9').format.font={name:'Arial',size:11,color:'#192B3B'};
guia.getRange('A:A').format.columnWidth=28;
guia.getRange('B:B').format.columnWidth=86;
guia.getRange('A1:B9').format.wrapText=true;
guia.getRange('A1:B9').format.rowHeight=36;
guia.getRange('A1:B1').format.font={name:'Arial',bold:true,size:13};
guia.showGridLines=false;
console.log((await wb.inspect({kind:'table',range:'Productos!A1:D3',include:'values',tableMaxRows:4,tableMaxCols:4})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A',options:{useRegex:true,maxResults:10}})).ndjson);
for(const [sheetName, range] of [['Productos','A1:D7'],['Guía','A1:B9']]){
 const preview=await wb.render({sheetName,range,scale:1.5,format:'png'});
 await fs.writeFile(path.join(output,`${sheetName}.png`),new Uint8Array(await preview.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(wb)).save(file);
console.log(file);
