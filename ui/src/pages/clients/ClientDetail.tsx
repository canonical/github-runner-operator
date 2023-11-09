import React, { FC } from "react";
import { Row } from "@canonical/react-components";
import { Link, useParams } from "react-router-dom";
import DeleteClientBtn from "pages/clients/DeleteClientBtn";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "util/queryKeys";
import EditClientBtn from "pages/clients/EditClientBtn";
import { NotificationConsumer } from "@canonical/react-components/dist/components/NotificationProvider/NotificationProvider";
import { fetchClient } from "api/client";

const ClientDetail: FC = () => {
  const { client: clientId } = useParams<{ client: string }>();

  if (!clientId) {
    return <></>;
  }

  const { data: client } = useQuery({
    queryKey: [queryKeys.clients, clientId],
    queryFn: () => fetchClient(clientId),
  });

  return (
    <div className="p-panel">
      <div className="p-panel__header ">
        <div className="p-panel__title">
          <nav
            key="breadcrumbs"
            className="p-breadcrumbs"
            aria-label="Breadcrumbs"
          >
            <ol className="p-breadcrumbs__items">
              <li className="p-breadcrumbs__item">
                <Link to="/client/list">Clients</Link>
              </li>
              <li className="p-breadcrumbs__item">Details</li>
            </ol>
          </nav>
        </div>
        {clientId && (
          <div className="p-panel__controls">
            {client && <DeleteClientBtn client={client} />}
            <EditClientBtn clientId={clientId} />
          </div>
        )}
      </div>
      <div className="p-panel__content">
        <Row>
          <h1 className="p-heading--4 u-no-margin--bottom">
            Client {clientId}
          </h1>
          <NotificationConsumer />
          <h2 className="p-heading--5">raw data:</h2>
          <code>{JSON.stringify(client)}</code>
        </Row>
      </div>
    </div>
  );
};

export default ClientDetail;
