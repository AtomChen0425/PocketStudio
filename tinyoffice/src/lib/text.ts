export function decodeUnicodeEscapes(text: string): string {
  if (!text.includes("\\u") && !text.includes("\\U")) return text;

  const decoded = text.replace(/\\u([0-9a-fA-F]{4})/g, (_match, hex: string) => {
    const codePoint = Number.parseInt(hex, 16);
    return Number.isFinite(codePoint) ? String.fromCharCode(codePoint) : _match;
  });

  return decoded.replace(/\\U([0-9a-fA-F]{8})/g, (_match, hex: string) => {
    const codePoint = Number.parseInt(hex, 16);
    return Number.isFinite(codePoint) ? String.fromCodePoint(codePoint) : _match;
  });
}
