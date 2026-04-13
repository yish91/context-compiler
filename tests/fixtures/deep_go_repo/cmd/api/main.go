package main

import (
	"example.com/api/internal/http"
	"github.com/gin-gonic/gin"
)

func main() {
	r := gin.Default()
	http.RegisterRoutes(r)
	r.Run(":8080")
}
