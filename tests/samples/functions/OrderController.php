<?php

namespace App\Http\Controllers;

#[Attribute]
abstract class OrderController extends Controller
{
    public function __construct(
        private readonly OrderRepository $orders,
        private readonly Mailer $mailer,
    ) {
    }

    #[Route('/orders/{id}', methods: ['GET'])]
    public function show(int $id): Response
    {
        // A brace in a comment: {
        $order = $this->orders->find($id); # and a hash comment }
        return response()->json(['id' => "{$order->id}", 'note' => '}']);
    }

    public static function &cache(): array
    {
        static $cache = [];
        return $cache;
    }

    abstract protected function handle(Request $request): void;

    private function filter(array $items): array
    {
        return array_filter($items, function ($item) {
            return $item !== null;
        });
    }
}

function helper($x)
{
    return $x;
}
