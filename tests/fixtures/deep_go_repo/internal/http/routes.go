package http

import "github.com/gin-gonic/gin"

func RegisterRoutes(r *gin.Engine) {
	v1 := r.Group("/api/v1")
	{
		v1.GET("/users", listUsers)
		v1.POST("/users", createUser)
	}
}

func listUsers(c *gin.Context) {
	c.JSON(200, gin.H{"users": []string{}})
}

func createUser(c *gin.Context) {
	c.JSON(201, gin.H{"created": true})
}
