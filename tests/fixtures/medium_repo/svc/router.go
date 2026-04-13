package main

import "net/http"

func healthHandler(w http.ResponseWriter, r *http.Request) {
    w.WriteHeader(http.StatusOK)
}

func metricsHandler(w http.ResponseWriter, r *http.Request) {
    w.Write([]byte("metrics"))
}

func eventsHandler(w http.ResponseWriter, r *http.Request) {
    w.Write([]byte("events"))
}
