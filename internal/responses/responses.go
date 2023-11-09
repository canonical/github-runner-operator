package responses

import "encoding/json"

type Response struct {
	Data    interface{} `json:"data"`
	Message string      `json:"message"`
	Status  int         `json:"status"`
	Links   interface{} `json:"_links"`
	Meta    interface{} `json:"_meta"`
}

func (r *Response) PrepareResponse() ([]byte, error) {
	resp, err := json.Marshal(r)
	if err != nil {
		return nil, err
	}
	return resp, err
}

func NewResponse(data interface{}, msg string, status int, links interface{}, meta interface{}) *Response {
	r := new(Response)
	r.Data = data
	r.Message = msg
	r.Status = status
	r.Links = links
	r.Meta = meta
	return r
}
