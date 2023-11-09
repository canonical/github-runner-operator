package responses

type Response struct {
	Data    interface{} `json:"data"`
	Message string      `json:"message"`
	Status  int         `json:"status"`
	Meta    interface{} `json:"_meta"`
}
