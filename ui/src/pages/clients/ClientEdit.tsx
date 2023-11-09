import React, { FC } from "react";
import { queryKeys } from "util/queryKeys";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import ClientEditForm from "pages/clients/ClientEditForm";
import { fetchClient } from "api/client";

const ClientEdit: FC = () => {
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
          <h1 className="p-heading--4 u-no-margin--bottom">Edit client</h1>
        </div>
      </div>
      <div className="p-panel__content">
        {client && <ClientEditForm client={client} />}
      </div>
    </div>
  );
};

export default ClientEdit;
