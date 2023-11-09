import React, { FC } from "react";
import { Button, Icon } from "@canonical/react-components";
import { useNavigate } from "react-router-dom";

interface Props {
  clientId: string;
}

const EditClientBtn: FC<Props> = ({ clientId }) => {
  const navigate = useNavigate();

  return (
    <Button
      appearance=""
      hasIcon
      onClick={() => navigate(`/client/edit/${clientId}`)}
    >
      <Icon name="edit" />
      <span>Edit</span>
    </Button>
  );
};

export default EditClientBtn;
