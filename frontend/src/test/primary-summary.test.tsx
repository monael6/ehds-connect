import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { fromSummary } from "@/lib/backend-mappers";
import { IpsCards } from "@/components/primary/shared";

afterEach(cleanup);

describe("Patient Summary medication codes", () => {
  it("shows ATC codes while hiding local fallback codes", () => {
    const patient = fromSummary({
      patient: {
        id: "P001",
        sex: "female",
        birth_date: "1950-01-01",
        age: 76,
        region: "Vienna",
        data_holder: "Klinikum West",
        opted_out_of_secondary_use: false,
      },
      medications: [
        { code: "C09AA05", system: "ATC", label: "Ramipril", dose: "5 mg" },
        { code: "P001-med-0", system: "local", label: "Unlisted medicine", dose: null },
      ],
    }, "en", { name: "Test patient", crossBorderOptIn: false });

    render(<IpsCards p={patient} lang="en" showCodes={false} showMedicationCodes />);

    expect(screen.getByText("ATC C09AA05")).toBeInTheDocument();
    expect(screen.queryByText("ATC P001-med-0")).not.toBeInTheDocument();
  });
});
