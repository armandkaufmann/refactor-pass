// The function declarations with a body that Go's own parser finds in a repo, as JSON: {path: [[name, first
// line, last line], ...]}. Usage: go run go_truth.go REPO
package main
import ("encoding/json";"go/ast";"go/parser";"go/token";"os";"path/filepath";"strings")
func main(){ repo:=os.Args[1]; out:=map[string][][]interface{}{}
 filepath.Walk(repo,func(p string,i os.FileInfo,e error)error{ if e!=nil||i.IsDir()||!strings.HasSuffix(p,".go"){return nil}
  fs:=token.NewFileSet(); f,err:=parser.ParseFile(fs,p,nil,0); if err!=nil{return nil}; rel,_:=filepath.Rel(repo,p); rows:=[][]interface{}{}
  for _,d:=range f.Decls{ if fn,ok:=d.(*ast.FuncDecl);ok&&fn.Body!=nil{ rows=append(rows,[]interface{}{fn.Name.Name,fs.Position(fn.Pos()).Line,fs.Position(fn.End()-1).Line}) } }
  out[rel]=rows; return nil}); json.NewEncoder(os.Stdout).Encode(out)}
