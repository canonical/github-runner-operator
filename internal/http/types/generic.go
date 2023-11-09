package types

import (
	"net/url"
	"strconv"
)

type Response struct {
	Data    interface{} `json:"data"`
	Message string      `json:"message"`
	Status  int         `json:"status"`
	Meta    *Pagination `json:"_meta"`
}

type Pagination struct {
	Page int64 `json:"page"`
	Size int64 `json:"size"`
}

func NewPaginationWithDefaults() *Pagination {
	p := new(Pagination)

	p.Page = 1
	p.Size = 100

	return p
}

func ParsePagination(q url.Values) *Pagination {

	p := NewPaginationWithDefaults()

	if page, err := strconv.ParseInt(q.Get("page"), 10, 64); err == nil && page > 1 {
		p.Page = page
	}

	if size, err := strconv.ParseInt(q.Get("size"), 10, 64); err == nil && size > 0 {
		p.Size = size
	}

	return p
}
