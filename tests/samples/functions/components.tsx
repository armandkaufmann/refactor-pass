import React from "react";
export const Card = ({
  title,
  children,
}: Props) => {
  return <div>{title}</div>;
};

export const Row: React.FC<RowProps> = ({ a, b }) => {
  return null;
};

const useThing = (a: number, b: string): Thing => {
  return x;
};

export const handler = async (
  req: Request,
  res: Response,
): Promise<void> => {
  res.end();
};

export const Memo = React.memo(function Memo({ a }: P) {
  return null;
});

export default function Page({
  params,
}: { params: { id: string } }) {
  return <Card title={params.id}>a / b</Card>;
}
