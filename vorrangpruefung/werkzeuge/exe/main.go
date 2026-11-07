// Vorrangprüfung Wolfsburg – Starter für Windows.
// Enthält den kompletten Rechner (HTML) und öffnet ihn im Standardbrowser.
// Keine Installation, keine Administratorrechte, keine Datenübertragung.
package main

import (
	_ "embed"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
)

//go:embed rechner.html
var page []byte

func main() {
	out := flag.String("out", "", "nur Datei schreiben (Test), nicht öffnen")
	flag.Parse()
	dir := ""
	if *out != "" {
		dir = *out
	} else if base := os.Getenv("LOCALAPPDATA"); base != "" {
		dir = filepath.Join(base, "Vorrangpruefung")
	} else {
		dir = filepath.Join(os.TempDir(), "Vorrangpruefung")
	}
	if err := os.MkdirAll(dir, 0o755); err != nil {
		fail(err)
	}
	// fester Pfad, damit Eingaben und Sprache im Browser gespeichert bleiben
	file := filepath.Join(dir, "Vorrangpruefung_Wolfsburg.html")
	if err := os.WriteFile(file, page, 0o644); err != nil {
		fail(err)
	}
	if *out != "" {
		fmt.Println(file)
		return
	}
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", file)
	case "darwin":
		cmd = exec.Command("open", file)
	default:
		cmd = exec.Command("xdg-open", file)
	}
	if err := cmd.Start(); err != nil {
		fail(err)
	}
}

func fail(err error) {
	if runtime.GOOS == "windows" {
		exec.Command("mshta", "javascript:alert('Vorrangprüfung konnte nicht gestartet werden: "+fmt.Sprint(err)+"');close()").Run()
	}
	os.Exit(1)
}
