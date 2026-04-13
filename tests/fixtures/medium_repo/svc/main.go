package main

import "net/http"

func bootstrap() http.Handler {
    mux := http.NewServeMux()
    mux.HandleFunc("/health", healthHandler)
    mux.HandleFunc("/metrics", metricsHandler)
    mux.HandleFunc("/events", eventsHandler)
    return mux
}
