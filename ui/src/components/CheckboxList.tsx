import React, { FC } from "react";
import { CheckboxInput, Col, Row } from "@canonical/react-components";

interface Props {
  label: string;
  values: string[];
  checkedValues: string[];
  toggleValue: (value: string) => void;
}

const CheckboxList: FC<Props> = ({
  label,
  values,
  checkedValues,
  toggleValue,
}) => {
  return (
    <Row className="u-sv2">
      <Col size={4}>{label}</Col>
      <Col size={8}>
        {values.map((value) => (
          <CheckboxInput
            key={value}
            label={value}
            checked={checkedValues.includes(value)}
            onChange={() => toggleValue(value)}
          />
        ))}
      </Col>
    </Row>
  );
};

export default CheckboxList;
