import React, { FC } from "react";
import { Button, Col, Row, useNotify } from "@canonical/react-components";
import { useFormik } from "formik";
import * as Yup from "yup";
import { queryKeys } from "util/queryKeys";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import ClientForm, { ClientFormTypes } from "pages/clients/ClientForm";
import { NotificationConsumer } from "@canonical/react-components/dist/components/NotificationProvider/NotificationProvider";
import SubmitButton from "components/SubmitButton";
import { Client } from "types/client";
import { updateClient } from "api/client";

interface Props {
  client: Client;
}

const ClientEditForm: FC<Props> = ({ client }) => {
  const navigate = useNavigate();
  const notify = useNotify();
  const queryClient = useQueryClient();

  const ClientEditSchema = Yup.object().shape({
    client_name: Yup.string().required("This field is required"),
  });

  const formik = useFormik<ClientFormTypes>({
    initialValues: {
      client_uri: client.client_uri,
      client_name: client.client_name,
      grant_types: client.grant_types,
      response_types: client.response_types,
      scope: client.scope,
      redirect_uris: client.redirect_uris,
      request_object_signing_alg: client.request_object_signing_alg,
    },
    validationSchema: ClientEditSchema,
    onSubmit: (values) => {
      updateClient(client.client_id, JSON.stringify(values))
        .then(() => {
          void queryClient.invalidateQueries({
            queryKey: [queryKeys.clients],
          });
          navigate(
            `/client/detail/${client.client_id}`,
            notify.queue(notify.success("Client updated")),
          );
        })
        .catch((e) => {
          formik.setSubmitting(false);
          notify.failure("Client update failed", e);
        });
    },
  });

  const submitForm = () => {
    void formik.submitForm();
  };

  return (
    <>
      <Row>
        <Col size={12}>
          <NotificationConsumer />
          <ClientForm formik={formik} />
        </Col>
      </Row>
      <hr />
      <Row className="u-align--right u-sv2">
        <Col size={12}>
          <Button
            appearance="base"
            className="u-no-margin--bottom u-sv2"
            onClick={() => navigate(`/client/detail/${client.client_id}`)}
          >
            Cancel
          </Button>
          <SubmitButton
            isSubmitting={formik.isSubmitting}
            isDisabled={!formik.isValid}
            onClick={submitForm}
            buttonLabel="Update client"
            className="u-no-margin--bottom"
          />
        </Col>
      </Row>
    </>
  );
};

export default ClientEditForm;
