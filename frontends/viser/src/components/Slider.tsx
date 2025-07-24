import React from "react";
import { GuiSliderMessage } from "../WebsocketMessages";
import { Slider, Flex, NumberInput } from "@mantine/core";
import { GuiComponentContext } from "../ControlPanel/GuiComponentContext";
import { ViserInputComponent } from "./common";
import { sliderDefaultMarks } from "./ComponentStyles.css";

export default function SliderComponent({
  uuid,
  value,
  props: {
    label,
    hint,
    visible,
    disabled,
    min,
    max,
    precision,
    step,
    _marks: marks,
  },
}: GuiSliderMessage) {
  const { setValue } = React.useContext(GuiComponentContext)!;
  if (!visible) return null;
  const updateValue = (value: number) => setValue(uuid, value);
  const input = (
    <Flex justify="space-between">
      <Slider
        id={uuid}
        className={marks === null ? sliderDefaultMarks : undefined}
        size="xs"
        thumbSize={0}
        radius="xs"
        style={{ flexGrow: 1 }}
        styles={(theme) => ({
          thumb: {
            height: "0.75rem",
            width: "0.5rem",
            background: theme.colors[theme.primaryColor][6],
          },
          trackContainer: {
            zIndex: 3,
            position: "relative",
          },
          markLabel: {
            transform: "translate(-50%, 0.05rem)",
            fontSize: "0.6rem",
            textAlign: "center",
          },
          mark: {
            transform: "scale(2)",
          },
        })}
        pt="0.3em"
        pb="0.2em"
        showLabelOnHover={false}
        min={min}
        max={max}
        step={step ?? undefined}
        precision={precision}
        value={value}
        onChange={updateValue}
        marks={
          marks === null
            ? [
                {
                  value: min,
                  // Show 2 decimal places
                  label: `${min.toFixed(2)}`,
                },
                {
                  value: max,
                  // Show 2 decimal places
                  label: `${max.toFixed(2)}`,
                },
              ]
            : marks
        }
        disabled={disabled}
      />
      <NumberInput
        value={value}
        onChange={(newValue) => {
          // Ignore empty values.
          newValue !== "" && updateValue(Number(newValue));
        }}
        size="xs"
        min={min}
        max={max}
        hideControls
        step={step ?? undefined}
        decimalScale={2}
        fixedDecimalScale={true}
        style={{ width: "3rem" }}
        styles={{
          input: {
            padding: "0.375em",
            letterSpacing: "-0.5px",
            minHeight: "1.875em",
            height: "1.875em",
          },
        }}
        ml="xs"
      />
    </Flex>
  );

  return (
    <ViserInputComponent {...{ uuid, hint, label }}>
      {input}
    </ViserInputComponent>
  );
}
