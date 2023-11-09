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
import { createClient } from "api/client";

const ClientCreate: FC = () => {
  const navigate = useNavigate();
  const notify = useNotify();
  const queryClient = useQueryClient();

  const ClientCreateSchema = Yup.object().shape({
    client_name: Yup.string().required("This field is required"),
  });

  const formik = useFormik<ClientFormTypes>({
    initialValues: {
      client_uri: "",
      client_name: "grafana",
      grant_types: ["authorization_code", "refresh_token"],
      response_types: ["code", "id_token"],
      scope: "openid offline_access email",
      redirect_uris: ["http://localhost:2345/login/generic_oauth"],
      request_object_signing_alg: "RS256",
    },
    validationSchema: ClientCreateSchema,
    onSubmit: (values) => {
      createClient(JSON.stringify(values))
        .then((result) => {
          void queryClient.invalidateQueries({
            queryKey: [queryKeys.clients],
          });
          const msg = `Client created. Id: ${result.client_id} Secret: ${result.client_secret}`;
          navigate("/client/list", notify.queue(notify.success(msg)));
        })
        .catch((e) => {
          formik.setSubmitting(false);
          notify.failure("Client creation failed", e);
        });
    },
  });

  const submitForm = () => {
    void formik.submitForm();
  };

  return (
    <div className="p-panel">
      <div className="p-panel__header ">
        <div className="p-panel__title">
          <h1 className="p-heading--4 u-no-margin--bottom">
            Create new client
          </h1>
        </div>
      </div>
      <div className="p-panel__content">
        <Row>
          <Col size={12}>
            <NotificationConsumer />
            <ClientForm formik={formik} />
          </Col>
        </Row>
        <hr />
        <Row className="u-align--right">
          <Col size={12}>
            <Button appearance="base" onClick={() => navigate("/client/list")}>
              Cancel
            </Button>
            <SubmitButton
              isSubmitting={formik.isSubmitting}
              isDisabled={!formik.isValid}
              onClick={submitForm}
              buttonLabel="Create"
            />
          </Col>
        </Row>
      </div>
    </div>
  );
};

export default ClientCreate;
