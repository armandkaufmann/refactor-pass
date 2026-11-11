package server

import "net/http"

// Server serves orders.
type Server struct {
	mux *http.ServeMux
}

func New() *Server {
	return &Server{mux: http.NewServeMux()}
}

func (s *Server) Handle(
	pattern string,
	handler http.HandlerFunc,
) {
	s.mux.HandleFunc(pattern, handler)
}

func Map[T any, U any](items []T, f func(T) U) []U {
	out := make([]U, 0, len(items))
	for _, item := range items {
		out = append(out, f(item))
	}
	return out
}

func braces() string {
	open := '{'
	raw := `}
{{`
	return string(open) + raw
}

var handler = func(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(200)
}
