export const isoTimeToString = (isoTime: string) => {
  return new Date(isoTime).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};
