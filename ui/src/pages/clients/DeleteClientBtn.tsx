import React, { FC, useState } from "react";
import { useNavigate } from "react-router-dom";
import { queryKeys } from "util/queryKeys";
import { useQueryClient } from "@tanstack/react-query";
import { ConfirmationButton, useNotify } from "@canonical/react-components";
import { deleteClient } from "api/client";
import { Client } from "types/client";

interface Props {
  client: Client;
}

const DeleteClientBtn: FC<Props> = ({ client }) => {
  const notify = useNotify();
  const queryClient = useQueryClient();
  const [isLoading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleDelete = () => {
    setLoading(true);
    deleteClient(client.client_id)
      .then(() => {
        navigate(
          "/client/list",
          notify.queue(notify.success(`Client ${client.client_name} deleted.`)),
        );
      })
      .catch((e) => {
        notify.failure("Client deletion failed", e);
      })
      .finally(() => {
        setLoading(false);
        void queryClient.invalidateQueries({
          queryKey: [queryKeys.clients],
        });
      });
  };

  return (
    <ConfirmationButton
      loading={isLoading}
      confirmationModalProps={{
        title: "Confirm delete",
        children: (
          <p>
            This will permanently delete client <b>{client.client_name}</b>.
          </p>
        ),
        confirmButtonLabel: "Delete client",
        onConfirm: handleDelete,
      }}
      title="Confirm delete"
      appearance="base"
    >
      Delete
    </ConfirmationButton>
  );
};

export default DeleteClientBtn;
