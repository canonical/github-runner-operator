import React, { FC } from "react";
import { Button, Col, MainTable, Row } from "@canonical/react-components";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "util/queryKeys";
import { Link, useNavigate } from "react-router-dom";
import { NotificationConsumer } from "@canonical/react-components/dist/components/NotificationProvider/NotificationProvider";
import { fetchClients } from "api/client";
import { isoTimeToString } from "util/date";

const ClientList: FC = () => {
  const navigate = useNavigate();

  const { data: clients = [] } = useQuery({
    queryKey: [queryKeys.clients],
    queryFn: fetchClients,
  });

  return (
    <div className="p-panel">
      <div className="p-panel__header ">
        <div className="p-panel__title">
          <h1 className="p-heading--4 u-no-margin--bottom">Clients</h1>
        </div>
        <div className="p-panel__controls">
          <Button
            appearance="positive"
            onClick={() => navigate("/client/create")}
          >
            Create client
          </Button>
        </div>
      </div>
      <div className="p-panel__content">
        <Row>
          <Col size={12}>
            <NotificationConsumer />
            <MainTable
              className="u-table-layout--auto"
              sortable
              responsive
              paginate={30}
              headers={[
                { content: "Id", sortKey: "id" },
                { content: "Name", sortKey: "name" },
                { content: "Response types" },
                { content: "Grant types" },
                { content: "Date" },
              ]}
              rows={clients.map((client) => {
                return {
                  columns: [
                    {
                      content: (
                        <Link to={`/client/detail/${client.client_id}`}>
                          {client.client_id}
                        </Link>
                      ),
                      role: "rowheader",
                      "aria-label": "Id",
                    },
                    {
                      content: client.client_name,
                      role: "rowheader",
                      "aria-label": "Name",
                    },
                    {
                      content: client.response_types.join(", "),
                      role: "rowheader",
                      "aria-label": "Response types",
                    },
                    {
                      content: client.grant_types.join(", "),
                      role: "rowheader",
                      "aria-label": "Grant types",
                    },
                    {
                      content: (
                        <>
                          <div>
                            Created: {isoTimeToString(client.created_at)}
                          </div>
                          <div className="u-text--muted">
                            Updated: {isoTimeToString(client.updated_at)}
                          </div>
                        </>
                      ),
                      role: "rowheader",
                      "aria-label": "Created",
                    },
                  ],
                  sortData: {
                    id: client.client_id,
                    name: client.client_name.toLowerCase(),
                  },
                };
              })}
            />
          </Col>
        </Row>
      </div>
    </div>
  );
};

export default ClientList;
