import fs from "fs";
import path from 'path';

runLocal();

async function runLocal(){
 await combineFiles("_includes/stories/");
}

async function combineFiles(folder){
	let files = fs.readdirSync(folder);
  files = files.filter( ( elm ) => elm.match(/.*\.(html?)/ig));

  let arr = [];

  for (var i = 0; i < files.length; i++) {
  //for (var i = 0; i < 1; i++) {
  	let fileName = files[i];
  	let filePath = folder + fileName;

  	
  	let data = fs.readFileSync(filePath, 'utf8');
  	data = data.replace("{% include gridlayer.html", "- fileName="+fileName);
  	data = data.replace("%}", "");
  	data = data.replace("=", ": ");
  	
  	arr.push(data);
  	
  	
  }

  //console.log(arr);

  fs.writeFile("./file.txt", arr.toString(), (err) => {  
	if (err) throw err;
	console.log('Saved!');
  });
}