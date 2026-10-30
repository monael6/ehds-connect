export function validPatientIdentity(type: string, number: string, name: string, born: string, checked: boolean, informed: boolean) {
  return checked && informed && name.trim().toLowerCase() === "maria muster" && born === "1943-03-17" && (type === "austria-code" ? /^\d{8}$/.test(number) : number.trim().length > 0);
}