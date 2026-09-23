$(document).ready(function() {
    let cart = [];

    // Function to update the cart display
    function updateCart() {
        $('#cartItems').empty();
        let subtotal = 0;

        // Update each item in the cart
        cart.forEach((item, index) => {
            subtotal += item.total;
            $('#cartItems').append(`
                <tr>
                    <td>${item.name}</td>
                    <td>₹${item.price.toFixed(2)}</td>
                    <td>
                        <div class="input-group input-group-sm" style="width: 100px;">
                            <button class="btn btn-outline-secondary minus-item" type="button" data-index="${index}">-</button>
                            <input type="number" class="form-control text-center quantity-input" 
                                   value="${item.quantity}" min="1" max="${item.stock}" data-index="${index}">
                            <button class="btn btn-outline-secondary plus-item" type="button" data-index="${index}">+</button>
                        </div>
                    </td>
                    <td>${item.expiry_date}</td>
                    <td>₹${item.total.toFixed(2)}</td>
                    <td>
                        <button class="btn btn-sm btn-danger remove-item" data-index="${index}">
                            <i class="bi bi-trash"></i>
                        </button>
                    </td>
                </tr>
            `);
        });

        // Calculate totals
        const discount = parseFloat($('#discount').val()) || 0;
        const tax = parseFloat($('#tax').val()) || 0;
        const grandTotal = subtotal - discount + tax;

        // Update display
        $('#subtotal').text(`₹${subtotal.toFixed(2)}`);
        $('#displayDiscount').text(`₹${discount.toFixed(2)}`);
        $('#displayTax').text(`₹${tax.toFixed(2)}`);
        $('#grandTotal').text(`₹${grandTotal.toFixed(2)}`);

        // Update hidden input with cart data
        $('#cart_items').val(JSON.stringify(cart));
    }

    // Add to cart button click handler
    $(document).on('click', '.add-to-cart', function() {
        const medicineId = $(this).data('id');
        const medicineName = $(this).data('name');
        const medicinePrice = parseFloat($(this).data('price'));
        const medicineStock = parseInt($(this).data('stock'));
        const medicineExpiry = new Date($(this).data('expiry')); // Capture expiry date
        const today = new Date(); // Get today's date

        // Check if the medicine is expired
        if (medicineExpiry < today) {
            alert('This medicine is expired and cannot be added to the cart!');
            return; // Exit the function if the medicine is expired
        }

        // Check if item already exists in cart
        const existingItem = cart.find(item => item.id === medicineId);

        if (existingItem) {
            // If item exists, check stock before increasing quantity
            if (existingItem.quantity < medicineStock) {
                existingItem.quantity += 1;
                existingItem.total = existingItem.quantity * existingItem.price;
            } else {
                alert('Cannot add more than available stock!');
                return;
            }
        } else {
            // If item doesn't exist, add it to cart
            if (medicineStock > 0) {
                cart.push({
                    id: medicineId,
                    name: medicineName,
                    price: medicinePrice,
                    quantity: 1,
                    total: medicinePrice,
                    stock: medicineStock,
                    expiry_date: medicineExpiry // Include expiry date
                });
            } else {
                alert('This medicine is out of stock!');
                return;
            }
        }

        updateCart();
    });

    // Minus button click handler
    $(document).on('click', '.minus-item', function() {
        const index = $(this).data('index');
        if (cart[index].quantity > 1) {
            cart[index].quantity -= 1;
            cart[index].total = cart[index].price * cart[index].quantity;
            updateCart();
        }
    });

    // Plus button click handler
    $(document).on('click', '.plus-item', function() {
        const index = $(this).data('index');
        if (cart[index].quantity < cart[index].stock) {
            cart[index].quantity += 1;
            cart[index].total = cart[index].price * cart[index].quantity;
            updateCart();
        } else {
            alert('Cannot add more than available stock!');
        }
    });

    // Quantity input change handler
    $(document).on('change', '.quantity-input', function() {
        const index = $(this).data('index');
        const newQuantity = parseInt($(this).val());

        if (newQuantity > 0 && newQuantity <= cart[index].stock) {
            cart[index].quantity = newQuantity;
            cart[index].total = cart[index].price * newQuantity;
            updateCart();
        } else {
            $(this).val(cart[index].quantity); // Revert to previous value
            alert('Quantity must be between 1 and available stock!');
        }
    });

    // Remove item button click handler
    $(document).on('click', '.remove-item', function() {
        const index = $(this).data('index');
        cart.splice(index, 1);
        updateCart();
    });

    // Clear cart button click handler
    $('#clearCart').click(function() {
        if (confirm('Are you sure you want to clear the cart?')) {
            cart = [];
            updateCart();
        }
    });

    // Form submission handler
    $('#billForm').on('submit', function(e) {
        // Check for expired medicines in the cart
        const today = new Date(); // Get today's date
        const hasExpiredMedicines = cart.some(item => new Date(item.expiry_date) < today);

        if (hasExpiredMedicines) {
            e.preventDefault(); // Prevent form submission
            alert('Cannot generate bill. There are expired medicines in the cart!');
            return; // Exit the function
        }

        if (cart.length === 0) {
            e.preventDefault();
            alert('Please add at least one medicine to the bill!');
        }
    });

    // Update totals when discount or tax changes
    $('#discount, #tax').on('input', function() {
        updateCart();
    });
});